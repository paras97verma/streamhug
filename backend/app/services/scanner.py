"""Scanner service — recursive, incremental media discovery.

Walks the media directory structure, identifies movies / TV shows / anime
based on folder hierarchy, probes technical metadata, fetches TMDB info
and artwork, then registers everything with the :class:`LibraryService`.

The scanner is *incremental*: it tracks which files it has already
processed (by media ID) and skips them on subsequent runs.  When a
source file is modified (different mtime → different media ID), the old
entry is implicitly replaced.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.cache.manager import CacheManager
from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.media import Episode, Media, MediaType, Season
from app.services.artwork import ArtworkService
from app.services.ffprobe.runner import FFprobeService
from app.services.hls import HLSService
from app.services.library import LibraryService
from app.services.metadata import MetadataService
from app.utils.filenames import (
    parse_anime_episode_filename,
    parse_movie_filename,
    parse_season_folder,
    parse_tv_episode_filename,
    clean_title,
)
from app.utils.media_identity import generate_media_id, generate_series_id
from app.utils.paths import is_video_file

logger = get_logger("scanner")


class ScannerService:
    """Recursive async media scanner with incremental processing."""

    def __init__(
        self,
        settings: Settings,
        ffprobe_service: FFprobeService,
        metadata_service: MetadataService,
        artwork_service: ArtworkService,
        library_service: LibraryService,
        cache_manager: CacheManager,
        hls_service: HLSService,
    ) -> None:
        self._settings = settings
        self._ffprobe = ffprobe_service
        self._metadata = metadata_service
        self._artwork = artwork_service
        self._library = library_service
        self._cache = cache_manager
        self._hls = hls_service
        self._scanned_ids: set[str] = set()

    async def scan(self) -> None:
        """Perform a full incremental scan of all media categories."""
        logger.info("Scan started")

        movies = await self._scan_movies()
        tv_shows = await self._scan_series(
            self._settings.tv_shows_dir, MediaType.TV_SHOW
        )
        anime = await self._scan_series(
            self._settings.anime_dir, MediaType.ANIME
        )

        self._library.rebuild(movies=movies, tv_shows=tv_shows, anime=anime)
        logger.info(
            "Scan complete — %d movies, %d TV shows, %d anime",
            len(movies), len(tv_shows), len(anime),
        )
        asyncio.create_task(self._warm_streaming_artifacts())

    # ── Movie scanning ───────────────────────────────────────────────────

    async def _scan_movies(self) -> list[Media]:
        """Scan the Movies directory for individual movie files."""
        movies_dir = self._settings.movies_dir
        if not movies_dir.is_dir():
            return []

        media_list: list[Media] = []
        tasks: list[asyncio.Task[Media | None]] = []

        for file_path in sorted(movies_dir.iterdir()):
            if not file_path.is_file() or not is_video_file(file_path):
                continue
            tasks.append(asyncio.create_task(self._process_movie(file_path)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Media):
                media_list.append(result)
            elif isinstance(result, Exception):
                logger.error("Movie processing error: %s", result)

        return media_list

    async def _process_movie(self, file_path: Path) -> Media | None:
        """Process a single movie file."""
        media_id = generate_media_id(file_path)

        parsed = parse_movie_filename(file_path)
        technical_info = await self._ffprobe.analyse(file_path, media_id)

        metadata = await self._metadata.fetch_metadata(
            media_id=media_id,
            title=parsed.title,
            year=parsed.year if parsed.year > 0 else None,
            media_type=MediaType.MOVIE,
            source_path=file_path,
        )

        poster_rel, banner_rel = await self._artwork.ensure_artwork(
            media_id=media_id,
            file_path=file_path,
            metadata=metadata,
        )

        title = metadata.get("title", parsed.title)
        year = metadata.get("year") or (parsed.year if parsed.year > 0 else None)

        return Media(
            media_id=media_id,
            title=title,
            year=year,
            media_type=MediaType.MOVIE,
            overview=metadata.get("overview", ""),
            file_path=file_path,
            technical_info=technical_info,
            poster_path=poster_rel,
            banner_path=banner_rel,
        )

    # ── Series scanning (TV Shows & Anime) ───────────────────────────────

    async def _scan_series(
        self, root_dir: Path, media_type: MediaType
    ) -> list[Media]:
        """Scan a series directory (TV Shows or Anime)."""
        if not root_dir.is_dir():
            return []

        media_list: list[Media] = []

        for series_dir in sorted(root_dir.iterdir()):
            if not series_dir.is_dir():
                continue
            try:
                series = await self._process_series(series_dir, media_type)
                if series is not None:
                    media_list.append(series)
            except Exception as exc:
                logger.error("Series processing error for %s: %s", series_dir.name, exc)

        return media_list

    async def _process_series(
        self, series_dir: Path, media_type: MediaType
    ) -> Media | None:
        """Process a single series directory."""
        series_id = generate_series_id(series_dir)
        series_title = clean_title(series_dir.name)

        seasons: list[Season] = []

        for season_dir in sorted(series_dir.iterdir()):
            if not season_dir.is_dir():
                continue
            season = await self._process_season(season_dir, media_type)
            if season is not None and season.episodes:
                seasons.append(season)

        if not seasons:
            return None

        # Use the first episode for metadata and artwork
        first_episode = seasons[0].episodes[0]
        metadata = await self._metadata.fetch_metadata(
            media_id=series_id,
            title=series_title,
            year=None,
            media_type=media_type,
            source_path=first_episode.file_path,
        )

        poster_rel, banner_rel = await self._artwork.ensure_artwork(
            media_id=series_id,
            file_path=first_episode.file_path,
            metadata=metadata,
        )

        return Media(
            media_id=series_id,
            title=metadata.get("title", series_title),
            year=metadata.get("year"),
            media_type=media_type,
            overview=metadata.get("overview", ""),
            seasons=seasons,
            poster_path=poster_rel,
            banner_path=banner_rel,
        )

    async def _process_season(
        self, season_dir: Path, media_type: MediaType
    ) -> Season | None:
        """Process a single season directory."""
        season_number = parse_season_folder(season_dir)
        episodes: list[Episode] = []
        tasks: list[asyncio.Task[Episode | None]] = []

        for file_path in sorted(season_dir.iterdir()):
            if not file_path.is_file() or not is_video_file(file_path):
                continue
            tasks.append(
                asyncio.create_task(
                    self._process_episode(file_path, season_dir, media_type)
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Episode):
                episodes.append(result)
            elif isinstance(result, Exception):
                logger.error("Episode processing error: %s", result)

        if not episodes:
            return None

        episodes.sort(key=lambda e: e.episode_number)
        return Season(season_number=season_number, episodes=episodes)

    async def _process_episode(
        self, file_path: Path, season_dir: Path, media_type: MediaType
    ) -> Episode | None:
        """Process a single episode file."""
        media_id = generate_media_id(file_path)

        if media_type == MediaType.ANIME:
            parsed = parse_anime_episode_filename(file_path, season_dir)
        else:
            parsed = parse_tv_episode_filename(file_path, season_dir)

        technical_info = await self._ffprobe.analyse(file_path, media_id)

        return Episode(
            media_id=media_id,
            title=parsed.title,
            season_number=parsed.season_number,
            episode_number=parsed.episode_number,
            file_path=file_path,
            technical_info=technical_info,
        )

    async def _warm_streaming_artifacts(self) -> None:
        """Prepare manifests and background jobs after scans complete.

        Preparing streaming artifacts right after discovery makes first playback
        feel instant because the first user is no longer blocked on manifest and
        queue setup.
        """
        for media_id in self._library.all_media_ids():
            source_path = self._library.get_file_path_for_id(media_id)
            if source_path is None or not source_path.is_file():
                continue
            try:
                await self._hls.ensure_media_ready(media_id, source_path)
            except Exception as exc:
                logger.debug("Streaming warm-up skipped for %s: %s", media_id, exc)
