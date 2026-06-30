"""Filename parsing utilities.

Extracts structured information from on-disk filenames following the
StreamHug naming conventions, with robust sanitization and title standardization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# ── Compiled patterns ────────────────────────────────────────────────────

_MOVIE_PATTERN = re.compile(
    r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)\s*$"
)

_TV_EPISODE_PATTERN = re.compile(
    r"^S(?P<season>\d{1,3})E(?P<episode>\d{1,3})"
    r"(?:\s*-\s*(?P<title>.+))?$",
    re.IGNORECASE,
)

_ANIME_EPISODE_PATTERN = re.compile(
    r"^EP(?P<episode>\d{1,4})"
    r"(?:\s*-\s*(?P<title>.+))?$",
    re.IGNORECASE,
)

_SEASON_FOLDER_PATTERN = re.compile(
    r"^Season\s+(?P<season>\d{1,3})$",
    re.IGNORECASE,
)

_YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")


# ── Result data classes ──────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class MovieInfo:
    """Parsed movie filename information."""

    title: str
    year: int


@dataclass(frozen=True, slots=True)
class EpisodeInfo:
    """Parsed episode filename information."""

    season_number: int
    episode_number: int
    title: str


# ── Clean & Standardize Utility ──────────────────────────────────────────

def clean_title(title: str) -> str:
    """Clean and standardize media titles, including downloader artifacts.

    Replaces separators (dots, underscores) with spaces, strips bracketed/parenthesized
    metadata (like resolutions, codecs, dual-audio markers), removes downloader prefixes/video IDs,
    and normalizes spacing and casing.
    """
    # 1. Remove bracketed metadata: [1080p], [HEVC], [Dual-Audio], etc.
    title = re.sub(r"\[[^\]]+\]", " ", title)
    
    # 2. Remove parentheses metadata except year (4-digit starting with 19 or 20)
    title = re.sub(r"\((?!(19\d{2}|20\d{2}))[^\)]+\)", " ", title)
    
    # 3. Strip common downloader prefixes (case-insensitive)
    prefixes = [
        r"^ytdown_youtube_", r"^ytdown_", r"^youtube_", r"^ytdl_", r"^ytdlp_", r"^yt_",
        r"^[a-zA-Z0-9-]+\.(vip|com|org|net|me|to|pw)\s*[-_]\s*",  # e.g. MoviezGuru.vip -
    ]
    for pref in prefixes:
        title = re.sub(pref, "", title, flags=re.IGNORECASE)
        
    # 4. Strip common downloader suffix/infix tags (case-insensitive)
    suffixes = [
        r"_media_", r"\bmedia\b"
    ]
    for suff in suffixes:
        title = re.sub(suff, " ", title, flags=re.IGNORECASE)
        
    # 5. Strip YouTube video IDs (11-character alphanumeric with dashes/underscores)
    title = re.sub(r"[-_][a-zA-Z0-9_-]{11}\b", " ", title)
    
    # 6. Remove common quality/codec/release tags
    tags = [
        r"\b1080p\b", r"\b720p\b", r"\b480p\b", r"\b360p\b", r"\b2160p\b", r"\b4k\b",
        r"\bbluray\b", r"\bbrrip\b", r"\bdvdrip\b", r"\bweb-dl\b", r"\bwebrip\b",
        r"\bx264\b", r"\bx265\b", r"\bhevc\b", r"\bh264\b", r"\bh265\b",
        r"\baac\b", r"\bdts\b", r"\bdd5\.1\b", r"\b5\.1\b", r"\bdual-audio\b",
        r"\bmulti-audio\b", r"\byts\b", r"\byify\b"
    ]
    for tag in tags:
        title = re.sub(tag, " ", title, flags=re.IGNORECASE)
        
    # 7. Strip trailing part/index numbers if they are just indexes (like _002 or _01)
    title = re.sub(r"[-_]\d{2,4}\b", " ", title)

    # 8. Standardize spaces around separators (dots, underscores) by replacing them first
    title = title.replace(".", " ").replace("_", " ")
    
    # 9. Clean up separator sequences like "- -" or " - -"
    title = re.sub(r"\s*-\s*", " - ", title)
    
    # 10. Replace the main title separator " - " with a token to protect it
    title = title.replace(" - ", "|||")
    
    # 11. Replace all other hyphens with spaces (e.g. SIFT-BHALWAAN -> SIFT BHALWAAN)
    title = title.replace("-", " ")
    
    # 12. Restore the protected main title separator
    title = title.replace("|||", " - ")
    
    # 13. Clean up double/multiple spaces and trailing spaces
    title = re.sub(r"\s+", " ", title).strip()
    
    # Remove leading/trailing separator dashes
    title = title.strip("-").strip()
    
    # 14. Capitalize words correctly (Title Case)
    return title.title()


# ── Public API ───────────────────────────────────────────────────────────

def parse_movie_filename(file_path: Path) -> MovieInfo:
    """Parse a movie filename into title and year.

    Args:
        file_path: Path to the movie file.

    Returns:
        A ``MovieInfo`` with the extracted title and year.
    """
    stem = file_path.stem
    
    # Try strict pattern: "Title (Year)"
    match = _MOVIE_PATTERN.match(stem)
    if match:
        title = match.group("title")
        year = int(match.group("year"))
        return MovieInfo(title=clean_title(title), year=year)
    
    # Try flexible pattern: find a year in the filename
    year_match = _YEAR_PATTERN.search(stem)
    if year_match:
        year = int(year_match.group(1))
        # Split stem at the year match start index
        idx = year_match.start()
        title = stem[:idx]
        # Strip trailing punctuation that belonged to the year (e.g. left parenthesis, dot)
        title = re.sub(r"[\(\[\{\.\-\s_]+$", "", title)
        return MovieInfo(title=clean_title(title), year=year)
        
    # Fallback: no year, just clean the stem
    return MovieInfo(title=clean_title(stem), year=0)


def parse_tv_episode_filename(file_path: Path, season_dir: Path) -> EpisodeInfo:
    """Parse a TV show episode filename.

    The season number is extracted from the parent ``Season XX`` folder.
    The episode number and optional title come from the filename itself.

    Args:
        file_path: Path to the episode file.
        season_dir: Path to the ``Season XX`` directory.

    Returns:
        An ``EpisodeInfo`` with season, episode, and title.
    """
    season_number = parse_season_folder(season_dir)
    stem = file_path.stem
    match = _TV_EPISODE_PATTERN.match(stem)
    if not match:
        return EpisodeInfo(
            season_number=season_number,
            episode_number=0,
            title=clean_title(stem),
        )
    
    ep_num = int(match.group("episode"))
    raw_title = match.group("title")
    title = clean_title(raw_title) if raw_title else f"Episode {ep_num}"
    
    return EpisodeInfo(
        season_number=int(match.group("season")),
        episode_number=ep_num,
        title=title,
    )


def parse_anime_episode_filename(file_path: Path, season_dir: Path) -> EpisodeInfo:
    """Parse an anime episode filename.

    Season number comes from the ``Season XX`` parent folder.
    Episode number from the ``EPxx`` prefix.

    Args:
        file_path: Path to the episode file.
        season_dir: Path to the ``Season XX`` directory.

    Returns:
        An ``EpisodeInfo`` with season, episode, and title.
    """
    season_number = parse_season_folder(season_dir)
    stem = file_path.stem
    match = _ANIME_EPISODE_PATTERN.match(stem)
    if not match:
        return EpisodeInfo(
            season_number=season_number,
            episode_number=0,
            title=clean_title(stem),
        )
        
    ep_num = int(match.group("episode"))
    raw_title = match.group("title")
    title = clean_title(raw_title) if raw_title else f"Episode {ep_num}"
    
    return EpisodeInfo(
        season_number=season_number,
        episode_number=ep_num,
        title=title,
    )


def parse_season_folder(season_dir: Path) -> int:
    """Extract the season number from a ``Season XX`` directory name.

    Args:
        season_dir: Path to a directory named ``Season 01``, etc.

    Returns:
        The numeric season number, or ``1`` as a fallback.
    """
    match = _SEASON_FOLDER_PATTERN.match(season_dir.name)
    if match:
        return int(match.group("season"))
    return 1
