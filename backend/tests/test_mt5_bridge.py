"""Pengujian integrasi MT5 Socket Bridge — SIMULASI (tanpa terminal MT5).

MockEA meniru EA MT5SocketClient di sisi lain kabel: membaca request JSON
+ newline dan membalas response JSON + newline sesuai protokol sumber
(huy-bui-tech/mt5_api). Tidak ada order yang dikirim dalam pengujian —
justru diuji bahwa perintah order MUSTAHIL terkirim.
"""
import asyncio
import json
import socket
import threading
import time

import pytest

from mt5_bridge_adapter import BridgeManager, ReadOnlyBridgeError
from mt5_bridge import MT5BridgeError
from mt5_bridge.protocol import Action

# ---------------------------------------------------------------- helpers
MOCK_DATA = {
    "GET_ACCOUNT": {"balance": 15000.50, "equity": 15100.00,
                    "margin": 250.00, "free_margin": 14850.00,
                    "leverage": 500},
    "GET_TICK": {"bid": 2650.10, "ask": 2650.40, "last": 2650.25,
                 "volume": 123, "time": "2026.10.11 12:00:00"},
    "GET_DATA": {"rates": [
        {"time": "2026.10.11 11:00:00", "open": 2648.0, "high": 2651.5,
         "low": 2647.2, "close": 2650.1, "volume": 950},
        {"time": "2026.10.11 12:00:00", "open": 2650.1, "high": 2652.0,
         "low": 2649.0, "close": 2650.8, "volume": 1100}]},
    "GET_POSITIONS": {"positions": [
        {"ticket": 900001, "symbol": "XAUUSD",
         "type": "POSITION_TYPE_BUY", "volume": 0.20,
         "open_price": 2630.00, "sl": 2620.00, "tp": 2680.00,
         "profit": 4.10}]},
    "GET_SYMBOLS": {"symbols": ["XAUUSD", "EURUSD", "BTCUSD"]},
    "HEARTBEAT": {},
}


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_port(port: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=0.2)
            s.close()
            return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("Bridge server tidak siap dalam batas waktu")


class MockEA:
    """Klien TCP peniru EA MT5 — menjawab perintah baca, mencatat action."""

    def __init__(self, port: int, fail_actions=()):
        self.port = port
        self.received: list[str] = []
        self.fail_actions = set(fail_actions)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=3)

    def _run(self) -> None:
        asyncio.run(self._main())

    async def _main(self) -> None:
        writer = None
        for _ in range(200):          # tunggu server bridge siap
            if self._stop.is_set():
                return
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
                break
            except OSError:
                await asyncio.sleep(0.05)
        if writer is None:
            return
        try:
            while not self._stop.is_set():
                try:
                    line = await asyncio.wait_for(reader.readline(), timeout=0.2)
                except asyncio.TimeoutError:
                    continue
                if not line:
                    break
                req = json.loads(line.decode())
                action = req.get("action", "")
                self.received.append(action)
                if action in self.fail_actions:
                    resp = {"id": req.get("id"), "success": False,
                            "error_code": 4756,
                            "error_message": "Invalid symbol (mock)",
                            "data": {}}
                else:
                    resp = {"id": req.get("id"), "success": True,
                            "error_code": 0, "error_message": "",
                            "data": MOCK_DATA.get(action, {})}
                writer.write((json.dumps(resp) + "\n").encode())
                await writer.drain()
        finally:
            try:
                writer.close()
            except Exception:
                pass


@pytest.fixture()
def bridge(client, monkeypatch):
    """Bridge berjalan di port bebas + MockEA terhubung.
    Endpoint Flask diarahkan ke manager fixture (bukan singleton)."""
    import config
    import app as app_mod
    monkeypatch.setattr(config, "MT5_BRIDGE_ENABLED", True)
    port = free_port()
    mgr = BridgeManager(host="127.0.0.1", port=port)
    mgr.start()
    monkeypatch.setattr(app_mod, "get_manager", lambda: mgr)
    ea = MockEA(port)
    ea.start()
    assert wait_connected(mgr), "MockEA tidak berhasil terhubung ke bridge"
    yield mgr, ea
    ea.stop()
    mgr.stop()


def wait_connected(mgr, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if mgr.status()["connected"]:
            return True
        time.sleep(0.05)
    return False


# ---------------------------------------------------------------- tests
def test_status_saat_bridge_mati(client):
    r = client.get("/api/trading/mt5bridge/status")
    assert r.status_code == 200
    d = r.get_json()
    assert d["enabled"] is False and d["read_only"] is True


def test_endpoint_data_menolak_saat_bridge_mati(client):
    r = client.get("/api/trading/mt5bridge/account")
    assert r.status_code == 503
    assert r.get_json()["error"]["code"] == "BRIDGE_DISABLED"


def test_format_error_konsisten(client):
    r = client.get("/api/trading/mt5bridge/price")
    d = r.get_json()
    assert "error" in d and "code" in d["error"] and "message" in d["error"]


def test_status_terhubung(client, bridge):
    mgr, _ea = bridge
    r = client.get("/api/trading/mt5bridge/status")
    d = r.get_json()
    assert r.status_code == 200
    assert d["enabled"] is True and d["running"] is True
    assert d["connected"] is True and d["read_only"] is True
    assert d["port"] == mgr._port


def test_account_dari_ea(client, bridge):
    _mgr, _ea = bridge
    r = client.get("/api/trading/mt5bridge/account")
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["balance"] == 15000.50 and d["equity"] == 15100.00
    assert d["margin"] == 250.00 and d["free_margin"] == 14850.00
    assert d["leverage"] == 500 and "note" in d


def test_harga_xauusd(client, bridge):
    _mgr, _ea = bridge
    r = client.get("/api/trading/mt5bridge/price?symbol=XAUUSD")
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["symbol"] == "XAUUSD"
    assert d["bid"] == 2650.10 and d["ask"] == 2650.40
    assert d["spread"] == 0.30


def test_harga_simbol_tidak_valid(client, bridge):
    _mgr, _ea = bridge
    r = client.get("/api/trading/mt5bridge/price?symbol=XX$$")
    assert r.status_code == 400
    assert r.get_json()["error"]["code"] == "VALIDATION"


def test_candles(client, bridge):
    _mgr, _ea = bridge
    r = client.get("/api/trading/mt5bridge/candles?symbol=XAUUSD&timeframe=H1&count=2")
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["timeframe"] == "H1" and d["count"] == 2
    assert len(d["rates"]) == 2
    assert d["rates"][0]["close"] == 2650.1


def test_candles_validasi(client, bridge):
    _mgr, _ea = bridge
    assert client.get("/api/trading/mt5bridge/candles?timeframe=H99").status_code == 400
    assert client.get("/api/trading/mt5bridge/candles?count=9999").status_code == 400
    assert client.get("/api/trading/mt5bridge/candles?count=abc").status_code == 400


def test_positions(client, bridge):
    _mgr, _ea = bridge
    r = client.get("/api/trading/mt5bridge/positions")
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["count"] == 1
    assert d["positions"][0]["ticket"] == 900001
    assert d["positions"][0]["volume"] == 0.20


def test_tanpa_ea_terhubung(client, monkeypatch):
    import config
    import app as app_mod
    monkeypatch.setattr(config, "MT5_BRIDGE_ENABLED", True)
    port = free_port()
    mgr = BridgeManager(host="127.0.0.1", port=port)
    mgr.start()
    monkeypatch.setattr(app_mod, "get_manager", lambda: mgr)
    try:
        time.sleep(0.5)          # pastikan tidak ada koneksi masuk
        assert not mgr.status()["connected"]
        r = client.get("/api/trading/mt5bridge/account")
        assert r.status_code == 503
        assert r.get_json()["error"]["code"] == "BRIDGE_DISCONNECTED"
    finally:
        mgr.stop()


def test_ea_membalas_error(client, monkeypatch):
    import config
    import app as app_mod
    monkeypatch.setattr(config, "MT5_BRIDGE_ENABLED", True)
    port = free_port()
    mgr = BridgeManager(host="127.0.0.1", port=port)
    mgr.start()
    monkeypatch.setattr(app_mod, "get_manager", lambda: mgr)
    ea = MockEA(port, fail_actions={"GET_TICK"})
    try:
        ea.start()
        assert wait_connected(mgr)
        r = client.get("/api/trading/mt5bridge/price?symbol=XAUUSD")
        assert r.status_code == 502
        assert r.get_json()["error"]["code"] == "BRIDGE_COMMAND"
    finally:
        ea.stop()
        mgr.stop()


def test_read_only_tidak_ada_order_terkirim(client, bridge):
    """Jaminan mutlak: hit semua endpoint baca, lalu coba order -> harus gagal
    TANPA perintah TRADE/CLOSE_POSITION pernah mencapai kabel."""
    mgr, ea = bridge
    assert client.get("/api/trading/mt5bridge/account").status_code == 200
    assert client.get("/api/trading/mt5bridge/price?symbol=XAUUSD").status_code == 200
    assert client.get("/api/trading/mt5bridge/candles?count=1").status_code == 200
    assert client.get("/api/trading/mt5bridge/positions").status_code == 200

    # coba order lewat API publik bridge object -> harus diblokir
    with pytest.raises(MT5BridgeError):
        mgr.call_fn(lambda b: b.buy("XAUUSD", 0.01))
    with pytest.raises(MT5BridgeError):
        mgr.call_fn(lambda b: b.close_position(900001))
    with pytest.raises(MT5BridgeError):
        mgr.call_fn(lambda b: b._send_command(Action.TRADE, {"symbol": "XAUUSD"}))

    time.sleep(0.2)
    assert "TRADE" not in ea.received
    assert "CLOSE_POSITION" not in ea.received
    # hanya perintah baca yang pernah lewat
    assert set(ea.received).issubset(set(MOCK_DATA))


def test_endpoint_lama_tetap_berfungsi(client):
    """Regresi: health + alur akun demo lama tidak terganggu bridge."""
    r = client.get("/api/trading/health")
    assert r.status_code == 200 and r.get_json()["ok"] is True
    acc = client.post("/api/trading/accounts",
                      json={"platform": "demo", "login": "uji-bridge"})
    assert acc.status_code == 201
    acc_id = acc.get_json()["account"]["id"]
    con = client.post("/api/trading/connect", json={"account_id": acc_id})
    assert con.status_code == 200
    s = client.get("/api/trading/summary?period=all")
    assert s.status_code == 200
