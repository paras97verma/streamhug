"""Core media domain models.

Strongly-typed Pydantic models representing the media entities within the
StreamHug library — movies, TV show episodes, anime episodes, seasons,
and the technical metadata extracted by FFprobe.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class MediaType(StrEnum):
    """Supported media categories mirroring the on-disk folder structure."""

    MOVIE = "movie"
    TV_SHOW = "tv_show"
    ANIME = "anime"


class AudioTrack(BaseModel):
    """A single audio track within a media file."""

    index: int = Field(description="Stream index within the file")
    language: str = Field(default="", description="Language code, e.g. 'eng'")
    title: str = Field(default="", description="Track title if available")
    codec: str = Field(default="", description="Audio codec name, e.g. 'aac'")
    channels: int = Field(default=2, description="Number of audio channels")


class SubtitleTrack(BaseModel):
    """A single subtitle/caption track within a media file."""

    index: int = Field(description="Stream index within the file")
    language: str = Field(default="", description="Language code, e.g. 'eng'")
    title: str = Field(default="", description="Track title if available")
    codec: str = Field(default="", description="Subtitle codec, e.g. 'subrip', 'ass'")


class MediaTechnicalInfo(BaseModel):
    """Technical metadata extracted from a media file via FFprobe."""

    duration_seconds: float = Field(description="Total duration in seconds")
    width: int = Field(description="Video width in pixels")
    height: int = Field(description="Video height in pixels")
    video_codec: str = Field(description="Video codec name, e.g. 'h264'")
    audio_codec: str = Field(default="", description="Primary audio codec name")
    bitrate_kbps: int = Field(default=0, description="Overall bitrate in kbps")
    frame_rate: float = Field(default=0.0, description="Video frame rate (fps)")
    file_size_bytes: int = Field(default=0, description="File size in bytes")
    audio_tracks: list[AudioTrack] = Field(
        default_factory=list, description="All embedded audio tracks"
    )
    subtitle_tracks: list[SubtitleTrack] = Field(
        default_factory=list, description="All embedded subtitle tracks"
    )


class Episode(BaseModel):
    """A single episode of a TV show or anime series."""

    media_id: str = Field(description="Unique deterministic identifier")
    title: str = Field(description="Episode display title")
    season_number: int = Field(ge=1, description="1-based season number")
    episode_number: int = Field(ge=1, description="1-based episode number")
    file_path: Path = Field(description="Absolute path to the media file")
    technical_info: MediaTechnicalInfo | None = Field(
        default=None, description="FFprobe-derived technical metadata"
    )


class Season(BaseModel):
    """An ordered collection of episodes within a series."""

    season_number: int = Field(ge=1, description="1-based season number")
    episodes: list[Episode] = Field(default_factory=list)

    @property
    def episode_count(self) -> int:
        return len(self.episodes)


class Media(BaseModel):
    """Top-level media item — a movie or a series (TV show / anime).

    For movies, ``file_path`` points to the single file and ``seasons`` is
    empty.  For series, ``file_path`` is ``None`` and episodes live inside
    ``seasons``.
    """

    media_id: str = Field(description="Unique deterministic identifier")
    title: str = Field(description="Display title")
    year: int | None = Field(default=None, description="Release year if known")
    media_type: MediaType
    overview: str = Field(default="", description="Plot summary")
    file_path: Path | None = Field(
        default=None, description="Absolute path (movies only)"
    )
    technical_info: MediaTechnicalInfo | None = Field(
        default=None, description="Technical metadata (movies only)"
    )
    seasons: list[Season] = Field(
        default_factory=list, description="Seasons (series only)"
    )
    poster_path: str = Field(default="", description="Relative poster cache path")
    banner_path: str = Field(default="", description="Relative banner cache path")

    @property
    def is_series(self) -> bool:
        return self.media_type in (MediaType.TV_SHOW, MediaType.ANIME)

    @property
    def total_episodes(self) -> int:
        return sum(s.episode_count for s in self.seasons)
