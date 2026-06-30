"""Library service — in-memory media registry.

Holds the current state of all scanned media and provides categorised
browsing, search, and lookup-by-ID functionality.  The library is rebuilt
atomically on each scan to avoid partial state.
"""

from __future__ import annotations

from pathlib import Path

from app.core.logging_config import get_logger
from app.models.library import Library, LibrarySummary
from app.models.media import Episode, Media

logger = get_logger("library")


class LibraryService:
    """Thread-safe in-memory media registry."""

    def __init__(self) -> None:
        self._library = Library()
        self._index: dict[str, Media] = {}
        self._episode_index: dict[str, tuple[Media, int, int]] = {}

    # ── Rebuild ──────────────────────────────────────────────────────────

    def rebuild(
        self,
        movies: list[Media],
        tv_shows: list[Media],
        anime: list[Media],
    ) -> None:
        """Atomically replace the library contents.

        Also rebuilds the media-ID → Media lookup index and the
        episode-ID → (parent Media, season_idx, episode_idx) index.
        """
        library = Library(movies=movies, tv_shows=tv_shows, anime=anime)
        index: dict[str, Media] = {}
        episode_index: dict[str, tuple[Media, int, int]] = {}

        for media in (*movies, *tv_shows, *anime):
            index[media.media_id] = media
            for season in media.seasons:
                for episode in season.episodes:
                    episode_index[episode.media_id] = (
                        media,
                        season.season_number,
                        episode.episode_number,
                    )

        # Atomic swap
        self._library = library
        self._index = index
        self._episode_index = episode_index

        logger.info("Library rebuilt — %d total items", library.total)

    # ── Queries ──────────────────────────────────────────────────────────

    @property
    def library(self) -> Library:
        """Return the current library state."""
        return self._library

    @property
    def count(self) -> int:
        """Total number of top-level media items."""
        return self._library.total

    @property
    def summary(self) -> LibrarySummary:
        """Return aggregate counts."""
        lib = self._library
        return LibrarySummary(
            movies=len(lib.movies),
            tv_shows=len(lib.tv_shows),
            anime=len(lib.anime),
            total=lib.total,
        )

    def get_by_id(self, media_id: str) -> Media | None:
        """Look up a top-level media item by its ID."""
        return self._index.get(media_id)

    def get_episode_by_id(self, media_id: str) -> Episode | None:
        """Look up an individual episode by its ID."""
        episode_info = self._episode_index.get(media_id)
        if episode_info is not None:
            parent, season_num, episode_num = episode_info
            for season in parent.seasons:
                if season.season_number == season_num:
                    for episode in season.episodes:
                        if episode.episode_number == episode_num:
                            return episode
        return None

    def get_file_path_for_id(self, media_id: str) -> Path | None:
        """Return the source file path for any media ID.

        Handles both top-level media (movies) and individual episodes.
        """
        # Check top-level media first
        media = self._index.get(media_id)
        if media is not None and media.file_path is not None:
            return media.file_path

        # Check episode index
        episode_info = self._episode_index.get(media_id)
        if episode_info is not None:
            parent, season_num, episode_num = episode_info
            for season in parent.seasons:
                if season.season_number == season_num:
                    for episode in season.episodes:
                        if episode.episode_number == episode_num:
                            return episode.file_path
        return None

    def search(self, query: str) -> list[Media]:
        """Search for media items by title (case-insensitive substring match).

        Args:
            query: The search term.

        Returns:
            A list of matching :class:`Media` items, ordered by relevance
            (exact prefix matches first, then substring matches).
        """
        if not query or not query.strip():
            return []

        term = query.strip().lower()
        prefix_matches: list[Media] = []
        substring_matches: list[Media] = []

        for media in self._index.values():
            title_lower = media.title.lower()
            if title_lower.startswith(term):
                prefix_matches.append(media)
            elif term in title_lower:
                substring_matches.append(media)

        prefix_matches.sort(key=lambda m: m.title.lower())
        substring_matches.sort(key=lambda m: m.title.lower())

        return prefix_matches + substring_matches

    def all_media_ids(self) -> set[str]:
        """Return the set of all tracked media IDs (top-level + episodes)."""
        return set(self._index.keys()) | set(self._episode_index.keys())
