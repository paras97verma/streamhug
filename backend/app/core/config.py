"""Application settings via pydantic-settings.

Loads configuration from environment variables and .env file.
Validates critical paths and external tool availability at startup.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised application configuration.

    All values can be overridden via environment variables or a ``.env`` file
    located in the project root (``be/``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ───────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    api_version: str = "v1"

    # ── Paths ────────────────────────────────────────────────────────────
    media_root: Path = Path("../media/originals")
    cache_root: Path = Path("../media/cache")
    log_dir: Path = Path("../logs")

    # ── TMDB ─────────────────────────────────────────────────────────────
    tmdb_api_key: str = ""
    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base_url: str = "https://image.tmdb.org/t/p"

    # ── HLS ──────────────────────────────────────────────────────────────
    hls_segment_duration: int = 3
    hls_max_concurrent_transcodes: int = 2
    hls_playlist_compression_min_size: int = 512
    hls_prefetch_segments: int = 3
    hls_stale_cleanup_age_seconds: int = 86_400
    hls_use_cmaf: bool = True
    hls_default_quality: str = "480p"

    # ── Scanner ──────────────────────────────────────────────────────────
    scan_on_startup: bool = True
    scan_interval_seconds: int = 300

    # ── Tunnel ───────────────────────────────────────────────────────────
    tunnel_enabled: bool = True
    tunnel_provider: Literal["none", "tunnelmole"] = "tunnelmole"
    tunnel_local_host: str = "127.0.0.1"
    tunnel_local_port: int | None = None
    tunnel_public_url: str = ""
    tunnel_healthcheck_seconds: int = 15
    tunnel_restart_delay_seconds: int = 5
    tunnel_command: str = "tmole"

    # ── WebSocket / realtime ────────────────────────────────────────────
    websocket_enabled: bool = True
    websocket_auth_token: str = ""
    websocket_heartbeat_seconds: int = 20

    # ── Redis / cache ───────────────────────────────────────────────────
    redis_url: str = ""
    redis_metadata_ttl_seconds: int = 3_600

    # ── Rate limiting ────────────────────────────────────────────────────
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 240
    rate_limit_window_seconds: int = 60

    # ── Authentication ───────────────────────────────────────────────────
    auth_enabled: bool = True
    auth_secret_key: str = "change-me-for-production"
    auth_access_token_ttl_seconds: int = 3_600
    auth_refresh_token_ttl_seconds: int = 2_592_000
    auth_verification_code_ttl_seconds: int = 900
    auth_verification_delivery: Literal["log", "inline"] = "log"
    auth_bootstrap_admin_email: str = ""
    auth_database_path: str = "auth.sqlite3"

    # ── Telemetry / metrics ──────────────────────────────────────────────
    metrics_enabled: bool = True
    playback_progress_ttl_seconds: int = 604_800
    healthcheck_ffmpeg_timeout_seconds: int = 5
    public_base_url: str = ""

    # ── Derived / computed ───────────────────────────────────────────────

    @property
    def api_prefix(self) -> str:
        """Return the full API route prefix, e.g. ``/api/v1``."""
        return f"/api/{self.api_version}"

    @property
    def tunnel_target_port(self) -> int:
        return self.tunnel_local_port or self.port

    @property
    def has_tmdb(self) -> bool:
        """Return True when a TMDB API key is configured."""
        return bool(self.tmdb_api_key.strip())

    @property
    def hls_cache_dir(self) -> Path:
        return self.cache_root / "hls"

    @property
    def poster_cache_dir(self) -> Path:
        return self.cache_root / "posters"

    @property
    def banner_cache_dir(self) -> Path:
        return self.cache_root / "banners"

    @property
    def thumbnail_cache_dir(self) -> Path:
        return self.cache_root / "thumbnails"

    @property
    def metadata_cache_dir(self) -> Path:
        return self.cache_root / "metadata"

    @property
    def auth_cache_dir(self) -> Path:
        return self.cache_root / "auth"

    @property
    def auth_db_path(self) -> Path:
        p = Path(self.auth_database_path)
        if p.is_absolute():
            return p
        return Path("/app") / p

    @property
    def movies_dir(self) -> Path:
        return self.media_root / "Movies"

    @property
    def tv_shows_dir(self) -> Path:
        return self.media_root / "TV Shows"

    @property
    def anime_dir(self) -> Path:
        return self.media_root / "Anime"

    # ── Validators ───────────────────────────────────────────────────────

    @model_validator(mode="after")
    def _resolve_paths(self) -> Self:
        """Resolve relative paths against the project root and ensure
        critical directories exist."""
        self.media_root = self.media_root.resolve()
        self.cache_root = self.cache_root.resolve()
        self.log_dir = self.log_dir.resolve()

        # Create cache sub-directories
        for directory in (
            self.hls_cache_dir,
            self.poster_cache_dir,
            self.banner_cache_dir,
            self.thumbnail_cache_dir,
            self.metadata_cache_dir,
            self.auth_cache_dir,
            self.log_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        # Create media category directories
        for directory in (self.movies_dir, self.tv_shows_dir, self.anime_dir):
            directory.mkdir(parents=True, exist_ok=True)

        if self.hls_segment_duration < 1:
            self.hls_segment_duration = 4
        if self.hls_prefetch_segments < 1:
            self.hls_prefetch_segments = 1
        if self.hls_max_concurrent_transcodes < 1:
            self.hls_max_concurrent_transcodes = 1
        if self.tunnel_healthcheck_seconds < 5:
            self.tunnel_healthcheck_seconds = 5
        if self.tunnel_restart_delay_seconds < 1:
            self.tunnel_restart_delay_seconds = 1
        if self.websocket_heartbeat_seconds < 5:
            self.websocket_heartbeat_seconds = 20
        if self.rate_limit_requests < 1:
            self.rate_limit_requests = 240
        if self.rate_limit_window_seconds < 1:
            self.rate_limit_window_seconds = 60
        if self.auth_access_token_ttl_seconds < 60:
            self.auth_access_token_ttl_seconds = 3_600
        if self.auth_refresh_token_ttl_seconds < 300:
            self.auth_refresh_token_ttl_seconds = 2_592_000
        if self.auth_verification_code_ttl_seconds < 60:
            self.auth_verification_code_ttl_seconds = 900

        return self

    def validate_startup(self) -> list[str]:
        """Return a list of warnings found during startup validation.

        An empty list means all checks passed.
        """
        warnings: list[str] = []

        if not shutil.which("ffmpeg"):
            warnings.append("ffmpeg not found on PATH")
        if not shutil.which("ffprobe"):
            warnings.append("ffprobe not found on PATH")
        if not self.media_root.is_dir():
            warnings.append(f"Media root does not exist: {self.media_root}")
        if not self.has_tmdb:
            warnings.append(
                "TMDB_API_KEY not set — artwork will be generated from video frames"
            )
        if self.tunnel_enabled and self.tunnel_provider == "tunnelmole":
            if not shutil.which(self.tunnel_command):
                warnings.append(
                    f"Tunnel provider '{self.tunnel_provider}' requested but "
                    f"'{self.tunnel_command}' was not found on PATH"
                )
        if self.auth_enabled and self.auth_secret_key == "change-me-for-production":
            warnings.append("AUTH_SECRET_KEY is using the default value")

        return warnings


def get_settings() -> Settings:
    """Factory that creates and returns a validated ``Settings`` instance."""
    return Settings()
