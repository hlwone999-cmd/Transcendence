#!/usr/bin/env python3
"""MockEA — peniru EA MT5SocketClient untuk uji koneksi TANPA Windows/MT5.

Menyambung ke bridge server (backend Flask) dan menjawab perintah baca
dengan data contoh. HANYA untuk pengujian — tidak ada order yang dikirim
atau dieksekusi.

Pakai (sambil backend berjalan dengan MT5_BRIDGE_ENABLED=1):
    python mt5_bridge/mock_ea.py --host 127.0.0.1 --port 1111
"""
import argparse
import asyncio
import json
import signal

MOCK = {
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
        {"ticket": 900001, "symbol": "XAUUSD", "type": "POSITION_TYPE_BUY",
         "volume": 0.20, "open_price": 2630.00, "sl": 2620.00,
         "tp": 2680.00, "profit": 4.10}]},
    "GET_SYMBOLS": {"symbols": ["XAUUSD", "EURUSD", "BTCUSD"]},
    "HEARTBEAT": {},
}


async def main(host: str, port: int) -> None:
    print(f"[mock-ea] menyambung ke {host}:{port} ...")
    reader, writer = None, None
    for attempt in range(200):
        try:
            reader, writer = await asyncio.open_connection(host, port)
            break
        except OSError:
            await asyncio.sleep(0.25)
    if writer is None:
        print("[mock-ea] gagal tersambung. Pastikan backend berjalan dengan "
              "MT5_BRIDGE_ENABLED=1.")
        return
    print("[mock-ea] TERHUBUNG. Menjawab perintah baca dengan data contoh. Ctrl+C untuk keluar.")
    try:
        while True:
            line = await reader.readline()
            if not line:
                print("[mock-ea] koneksi ditutup oleh bridge.")
                break
            req = json.loads(line.decode())
            action = req.get("action", "")
            print(f"[mock-ea] <- {action} {req.get('params', {})}")
            resp = {"id": req.get("id"), "success": True, "error_code": 0,
                    "error_message": "", "data": MOCK.get(action, {})}
            writer.write((json.dumps(resp) + "\n").encode())
            await writer.drain()
    except KeyboardInterrupt:
        pass
    finally:
        writer.close()
        print("[mock-ea] keluar.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Mock EA MT5 untuk uji bridge (read-only)")
    ap.add_argument("--host", default="127.0.0.1", help="alamat bridge server")
    ap.add_argument("--port", type=int, default=1111, help="port bridge server")
    args = ap.parse_args()
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        pass
