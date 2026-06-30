"""Tunnel provider abstraction and TunnelMole supervision."""

from __future__ import annotations

import asyncio
import contextlib
import re
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

from app.core.config import Settings
from app.core.logging_config import get_logger

logger = get_logger("tunnel")

PUBLIC_URL_RE = re.compile(r"(https://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")


@dataclass(slots=True)
class TunnelState:
    provider: str
    enabled: bool
    connected: bool = False
    public_url: str = ""
    last_error: str = ""
    restart_count: int = 0
    last_started_at: float | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class TunnelProvider(ABC):
    """Provider contract so additional tunnel implementations stay pluggable."""

    name: str

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def current_url(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def is_running(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def last_error(self) -> str:
        raise NotImplementedError


class TunnelMoleProvider(TunnelProvider):
    """Manages a local TunnelMole subprocess."""

    name = "tunnelmole"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._process: asyncio.subprocess.Process | None = None
        self._public_url = settings.tunnel_public_url
        self._last_error = ""
        self._reader_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._process is not None and self._process.returncode is None:
            return

        cmd = [
            self._settings.tunnel_command,
            str(self._settings.tunnel_target_port),
        ]
        logger.info("Starting TunnelMole with command: %s", " ".join(cmd))
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._reader_task = asyncio.create_task(self._consume_logs())

    async def _consume_logs(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return

        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                message = line.decode(errors="replace").strip()
                if not message:
                    continue
                logger.info("TunnelMole: %s", message)
                match = PUBLIC_URL_RE.search(message)
                if match:
                    self._public_url = match.group(1)
                    self._last_error = ""
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning("TunnelMole log reader failed: %s", exc)

    async def stop(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None

        if self._process is not None and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
        self._process = None

    def current_url(self) -> str:
        return self._public_url

    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    def last_error(self) -> str:
        if self._process is not None and self._process.returncode not in (None, 0):
            return f"TunnelMole exited with code {self._process.returncode}"
        return self._last_error


class NullTunnelProvider(TunnelProvider):
    name = "none"

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    def current_url(self) -> str:
        return ""

    def is_running(self) -> bool:
        return False

    def last_error(self) -> str:
        return ""


class TunnelService:
    """Supervises the configured tunnel provider and auto-reconnects on failure."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provider = self._build_provider(settings)
        self._state = TunnelState(
            provider=self._provider.name,
            enabled=settings.tunnel_enabled and self._provider.name != "none",
            public_url=settings.tunnel_public_url,
        )
        self._supervisor_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def _build_provider(self, settings: Settings) -> TunnelProvider:
        if not settings.tunnel_enabled or settings.tunnel_provider == "none":
            return NullTunnelProvider()
        return TunnelMoleProvider(settings)

    async def start(self) -> None:
        if not self._state.enabled:
            return
        self._stop_event.clear()
        if self._supervisor_task is None or self._supervisor_task.done():
            self._supervisor_task = asyncio.create_task(self._supervise())

    async def _supervise(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._state.last_started_at = time.time()
                await self._provider.start()
                await asyncio.sleep(2)
                self._state.connected = self._provider.is_running()
                self._state.public_url = self._provider.current_url()
                self._state.last_error = self._provider.last_error()

                while not self._stop_event.is_set():
                    await asyncio.sleep(self._settings.tunnel_healthcheck_seconds)
                    self._state.connected = self._provider.is_running()
                    self._state.public_url = self._provider.current_url()
                    self._state.last_error = self._provider.last_error()
                    if not self._state.connected:
                        raise RuntimeError(
                            self._state.last_error or "Tunnel provider stopped unexpectedly"
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._state.connected = False
                self._state.last_error = str(exc)
                self._state.restart_count += 1
                logger.warning("Tunnel reconnect scheduled: %s", exc)
                await self._provider.stop()
                await asyncio.sleep(self._settings.tunnel_restart_delay_seconds)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._supervisor_task is not None:
            self._supervisor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._supervisor_task
            self._supervisor_task = None
        await self._provider.stop()
        self._state.connected = False

    def state(self) -> TunnelState:
        self._state.public_url = self._provider.current_url() or self._state.public_url
        self._state.connected = self._provider.is_running()
        self._state.last_error = self._provider.last_error()
        return self._state
