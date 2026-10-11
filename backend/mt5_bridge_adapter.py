"""Adapter MT5 Socket Bridge untuk backend Flask kalkulator XAUUSD.

Integrasi paket mt5_bridge (adaptasi huy-bui-tech/mt5_api) ke Flask yang
sinkron, dengan aturan mutlak READ-ONLY:

- MT5Bridge berjalan di thread terpisah dengan event loop asyncio sendiri.
- Flask mengirim perintah lewat asyncio.run_coroutine_threadsafe.
- Hanya perintah BACA yang diizinkan: HEARTBEAT, GET_ACCOUNT, GET_TICK,
  GET_DATA, GET_POSITIONS, GET_SYMBOLS.
- TRADE / CLOSE_POSITION diblokir DI DUA LAPIS: override metode order
  (tidak pernah menulis apa pun ke socket) dan guard di _send_command.

Konfigurasi via env (lihat backend/config.py):
  MT5_BRIDGE_ENABLED=1  MT5_BRIDGE_HOST=127.0.0.1  MT5_BRIDGE_PORT=1111
"""
from __future__ import annotations

import asyncio
import dataclasses
import threading
import time

import config

# Paket bridge ada di root proyek, bukan di backend/
import sys
sys.path.insert(0, str(config.PROJECT_ROOT))

from mt5_bridge import (  # noqa: E402
    MT5Bridge,
    MT5BridgeError,
    NotConnectedError,
    TradeError,
)
from mt5_bridge.protocol import Action  # noqa: E402

COMMAND_SUBMIT_TIMEOUT = 40.0  # detik (di atas COMMAND_TIMEOUT bridge = 30s)

READ_ONLY_ACTIONS = {
    Action.HEARTBEAT,
    Action.GET_ACCOUNT,
    Action.GET_TICK,
    Action.GET_DATA,
    Action.GET_POSITIONS,
    Action.GET_SYMBOLS,
}
BLOCKED_ACTIONS = {Action.TRADE, Action.CLOSE_POSITION}


class ReadOnlyBridgeError(MT5BridgeError):
    """Dibangkitkan saat mencoba operasi order pada mode read-only."""


class ReadOnlyMT5Bridge(MT5Bridge):
    """MT5Bridge yang memblokir SEMUA operasi order.

    Lapis 1: metode order dioverride dan langsung error tanpa menyentuh
    socket. Lapis 2: _send_command menolak Action.TRADE/CLOSE_POSITION
    sehingga tidak ada jalur lain yang bisa mengirim perintah order.
    """

    async def buy(self, *args, **kwargs):  # noqa: D102
        raise ReadOnlyBridgeError("Mode read-only: order BUY dinonaktifkan.")

    async def sell(self, *args, **kwargs):  # noqa: D102
        raise ReadOnlyBridgeError("Mode read-only: order SELL dinonaktifkan.")

    async def place_pending_order(self, *args, **kwargs):  # noqa: D102
        raise ReadOnlyBridgeError("Mode read-only: pending order dinonaktifkan.")

    async def close_position(self, *args, **kwargs):  # noqa: D102
        raise ReadOnlyBridgeError("Mode read-only: penutupan posisi dinonaktifkan.")

    async def modify_position(self, *args, **kwargs):  # noqa: D102
        raise ReadOnlyBridgeError("Mode read-only: modifikasi posisi dinonaktifkan.")

    async def _send_command(self, action: Action, params: dict) -> dict:
        if action in BLOCKED_ACTIONS:
            raise ReadOnlyBridgeError(
                f"Mode read-only: perintah {action.value} tidak diizinkan.")
        return await super()._send_command(action, params)


class BridgeManager:
    """Menjalankan ReadOnlyMT5Bridge di thread asyncio dan menjembatani Flask."""

    def __init__(self, host: str | None = None, port: int | None = None):
        self._host = (host if host is not None else config.MT5_BRIDGE_HOST)
        self._port = int(port if port is not None else config.MT5_BRIDGE_PORT)
        self._bridge: ReadOnlyMT5Bridge | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.last_error = ""
        self.started_at = 0.0

    # ---- lifecycle -------------------------------------------------
    def start(self) -> None:
        """Mulai server TCP bridge di thread belakang (idempoten)."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._bridge = ReadOnlyMT5Bridge(host=self._host, port=self._port)
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._run, name="mt5-bridge", daemon=True)
            self.started_at = time.time()
            self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._bridge.start())
            self._loop.run_forever()
        except Exception as exc:  # pragma: no cover - kegagalan bind port dkk.
            self.last_error = str(exc)
        finally:
            try:
                self._loop.run_until_complete(self._bridge.stop())
            except Exception:
                pass
            self._loop.close()

    def stop(self) -> None:
        with self._lock:
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread:
                self._thread.join(timeout=5)
            self._loop = None
            self._bridge = None
            self._thread = None

    # ---- akses ------------------------------------------------------
    def call(self, coro):
        """Jalankan coroutine di loop bridge, blokir sampai selesai."""
        if not (self._loop and self._bridge):
            raise NotConnectedError("Bridge belum berjalan.")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return fut.result(timeout=COMMAND_SUBMIT_TIMEOUT)
        except asyncio.TimeoutError:
            fut.cancel()
            raise TimeoutError("Perintah bridge melebihi batas waktu.")

    def call_fn(self, fn):
        """Jalankan fn(bridge) -> coroutine di loop bridge (aman dari thread Flask)."""
        if not (self._loop and self._bridge):
            raise NotConnectedError(
                "Bridge belum berjalan atau belum selesai start.")
        fut = asyncio.run_coroutine_threadsafe(fn(self._bridge), self._loop)
        try:
            return fut.result(timeout=COMMAND_SUBMIT_TIMEOUT)
        except asyncio.TimeoutError:
            fut.cancel()
            raise TimeoutError("Perintah bridge melebihi batas waktu.")

    def status(self) -> dict:
        bridge = self._bridge
        connected = bool(bridge and bridge.is_connected)
        ea_address = None
        if bridge and bridge._server.connection is not None:
            ea_address = str(bridge._server.connection.client_address)
        return {
            "enabled": bool(config.MT5_BRIDGE_ENABLED),
            "running": bool(self._thread and self._thread.is_alive()),
            "connected": connected,
            "read_only": True,
            "host": self._host,
            "port": self._port,
            "ea_address": ea_address,
            "last_error": self.last_error,
        }

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())


_manager: BridgeManager | None = None


def get_manager() -> BridgeManager:
    """Singleton manager sesuai konfigurasi env."""
    global _manager
    if _manager is None:
        _manager = BridgeManager()
        if config.MT5_BRIDGE_ENABLED:
            _manager.start()
    return _manager


def to_dict(obj) -> dict:
    """Dataclass bridge -> dict JSON-aman."""
    return dataclasses.asdict(obj) if dataclasses.is_dataclass(obj) else obj
