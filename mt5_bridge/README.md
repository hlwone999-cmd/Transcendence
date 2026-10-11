# mt5_bridge — adaptasi kalkulator-xauusd

Paket ini adalah adaptasi komponen inti dari proyek
[huy-bui-tech/mt5_api](https://github.com/huy-bui-tech/mt5_api)
(MT5-Python Socket Bridge, lisensi MIT).

## Yang diintegrasikan

| Folder | Asal | Catatan |
|---|---|---|
| `protocol/` | salinan langsung | model & serialisasi JSON + newline |
| `server/` | salinan langsung | TCP server asyncio, 1 koneksi EA |
| `trading/` | salinan + adaptasi | import `timing` dibuat opsional (modul timing tidak disalin) |
| `ea/MT5SocketClient.mq5` | salinan langsung | EA untuk terminal MT5 di Windows |
| `mock_ea.py` | baru | peniru EA untuk pengujian tanpa Windows |

## Yang TIDAK disalin (sengaja)

- `mt5_bridge/ui/` — panel order Tkinter (fitur TRADING; integrasi ini read-only).
- `mt5_bridge/timing/` — pengukuran latensi (tidak dipakai; import dibuat opsional).
- `requirements.txt` sumber — berisi dependensi UI/telegram/aiohttp yang tidak
  diperlukan; inti bridge cukup stdlib Python.

## Lisensi & kredit

Kode sumber milik [huy-bui-tech](https://github.com/huy-bui-tech) (MIT).
Adaptasi untuk kalkulator-xauusd: import timing opsional, tanpa perubahan
protokol, plus guard read-only di `backend/mt5_bridge_adapter.py`.

Panduan pemakaian: `docs/MT5-BRIDGE.md`.
