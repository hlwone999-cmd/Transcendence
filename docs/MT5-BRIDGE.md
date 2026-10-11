# Integrasi MT5 API Bridge (read-only)

Integrasi bridge MetaTrader 5 dari [huy-bui-tech/mt5_api](https://github.com/huy-bui-tech/mt5_api)
(lisensi MIT) ke Kalkulator XAUUSD. Sifatnya **read-only murni**: hanya membaca
status koneksi, info akun, harga, candle, dan posisi terbuka. **Tidak ada
jalur kode yang bisa mengirim order BUY/SELL** — ditegakkan dua lapis di
`backend/mt5_bridge_adapter.py` dan diuji otomatis.

## Arsitektur

```
┌──────────────────────────┐  TCP  ┌─────────────────────┐  HTTP  ┌─────────────────┐
│ Terminal MT5 (Windows/   │ ────► │ Backend Flask       │ ◄────► │ APK / Browser   │
│ VPS) + EA                │       │ kalkulator XAUUSD   │        │ (fetch JSON)    │
│ MT5SocketClient.mq5      │       │ + server bridge     │        │                 │
│ (klien socket)           │       │ (thread asyncio)    │        │                 │
└──────────────────────────┘       └─────────────────────┘        └─────────────────┘
        sisi Windows                        sisi Linux/Android/Termux
```

Poin kunci (sesuai batasan MQL5 — socket hanya bisa CLIENT di sisi EA):

- **EA = klien**: `MT5SocketClient.mq5` di terminal MT5 menyambung KELUAR ke
  server bridge. Port bridge harus terbuka di mesin yang menjalankan backend.
- **Server bridge = Python stdlib saja** (asyncio): boleh dijalankan di
  Android/Termux, Linux, macOS, atau Windows — TANPA paket `MetaTrader5`.
- **Backend Flask** menampung server bridge di thread terpisah dan
  mengekspos endpoint HTTP JSON untuk APK/web.

## File yang ditambahkan / diubah

| File | Status | Isi |
|---|---|---|
| `mt5_bridge/protocol/` | baru (salinan inti) | model JSON, serialisasi, buffer |
| `mt5_bridge/server/` | baru (salinan inti) | TCP server asyncio |
| `mt5_bridge/trading/` | baru (salinan inti, timing opsional) | API high-level `MT5Bridge` |
| `mt5_bridge/ea/MT5SocketClient.mq5` | baru (salinan sumber) | EA untuk terminal MT5 |
| `mt5_bridge/mock_ea.py` | baru | peniru EA untuk uji tanpa Windows |
| `mt5_bridge/README.md` | baru | kredit sumber + catatan adaptasi |
| `backend/mt5_bridge_adapter.py` | baru | thread asyncio + guard read-only + mapping error |
| `backend/config.py` | diubah | 3 env var bridge |
| `backend/app.py` | diubah | 5 endpoint `/api/trading/mt5bridge/*` + startup |
| `backend/.env.example` | diubah | contoh env bridge |
| `backend/tests/test_mt5_bridge.py` | baru | 14 test simulasi (MockEA) |
| `docs/MT5-BRIDGE.md` | baru | dokumen ini |

Tidak ada file kalkulator (`index.html`, `style.css`, `script.js`) yang
diubah. Workflow GitHub Actions APK tidak diubah — APK tetap memuat
kalkulator dan build tetap jalan; endpoint baru tinggal dipanggil dari
WebView bila suatu saat diinginkan.

## Dependensi

- Python 3.9+ (diuji di 3.12; kompatibel Python 3.14 di Termux karena
  inti bridge memakai stdlib: asyncio, json, dataclasses, uuid).
- Backend tetap butuh `flask` + `cryptography` (requirements yang sudah ada).
- **Tidak** butuh paket `MetaTrader5` (itu Windows-only) untuk jalur bridge.
- EA butuh terminal MT5 di Windows (atau Wine) karena memakai Winsock
  (`ws2_32.dll`) — izinkan **"Allow DLL imports"** saat memasang EA.

## A. Sisi Windows / VPS — menjalankan MT5 + EA

1. Salin `mt5_bridge/ea/MT5SocketClient.mq5` ke folder
   `MQL5\Experts\` terminal MT5 (File → Open Data Folder).
2. Buka MetaEditor → compile (F7).
3. MT5: **Tools → Options → Expert Advisors** → centang
   *Allow WebRequest for listed URL* dan tambahkan IP mesin backend,
   mis. `http://192.168.1.50`.
4. Pasang EA ke grafik mana pun; isi input:
   - `ServerAddress` = IP mesin backend (mis. `192.168.1.50` atau IP publik VPS)
   - `ServerPort` = `1111` (samakan dengan `MT5_BRIDGE_PORT`)
   - `TimerIntervalMs` = 10 (polling), `HeartbeatIntervalMs` = 10000.
5. Pastikan "Algo Trading" aktif di toolbar (EA perlu status berjalan),
   firewall Windows mengizinkan koneksi keluar, dan (bila lintas mesin)
   firewall mesin backend mengizinkan port `1111`.

## B. Sisi Android / Termux atau Linux — menjalankan backend + bridge

```bash
# Termux:
pkg install python git
python -m venv ~/venv && source ~/venv/bin/activate

# masuk folder repo (clone atau hasil git pull)
cd kalkulator-xauusd
pip install -r backend/requirements.txt

# konfigurasi env (contoh minimal)
export MT5_BRIDGE_ENABLED=1
export MT5_BRIDGE_HOST=127.0.0.1        # lihat catatan keamanan bila lintas mesin
export MT5_BRIDGE_PORT=1111
export TRADING_SECRET_KEY="$(python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')"

# jalankan backend + bridge (bridge mulai otomatis)
python backend/app.py
```

Backend tersedia di `http://127.0.0.1:5000`; bridge mendengarkan di
`127.0.0.1:1111` dan menunggu EA tersambung.

> **Android/Termux**: backend + bridge berjalan baik (stdlib). Terminal MT5
> TIDAK bisa jalan di Termux — EA harus tetap di Windows/VPS. Bila backend di
> Termux dan MT5 di PC yang sama jaringan lokal: set `MT5_BRIDGE_HOST` ke
> `0.0.0.0` (atau IP LAN) dan buka port di firewall — baca bagian keamanan.

## Endpoint baru (semuanya read-only, format error konsisten)

| Endpoint | Param | Isi |
|---|---|---|
| `GET /api/trading/mt5bridge/status` | – | enabled/running/connected/read_only/host/port/ea_address |
| `GET /api/trading/mt5bridge/account` | – | balance, equity, margin, free_margin, leverage |
| `GET /api/trading/mt5bridge/price` | `symbol` (default XAUUSD) | bid, ask, last, volume, time, spread |
| `GET /api/trading/mt5bridge/candles` | `symbol`, `timeframe` (M1..MN1), `count` ≤2000 | deret OHLC |
| `GET /api/trading/mt5bridge/positions` | – | posisi terbuka (ticket, symbol, volume, sl/tp, profit) |

Contoh:

```bash
curl http://127.0.0.1:5000/api/trading/mt5bridge/status
curl "http://127.0.0.1:5000/api/trading/mt5bridge/price?symbol=XAUUSD"
curl "http://127.0.0.1:5000/api/trading/mt5bridge/candles?symbol=XAUUSD&timeframe=H1&count=100"
```

Bila `TRADING_API_TOKEN` diset, tambahkan header
`Authorization: Bearer <token>` (berlaku juga untuk endpoint bridge).

Catatan jujur soal data: protokol sumber `GET_ACCOUNT` hanya mengirim
balance/equity/margin/free_margin/leverage. **Nama server broker, jenis akun
(demo/real), dan mata uang tidak tersedia** lewat bridge ini — endpoint
`account` menandai hal itu di field `note`.

## Menghubungkan APK

Endpoint berformat JSON sama seperti endpoint lama, sehingga WebView/APK cukup
melakukan `fetch` ke `http://<ip-backend>:5000/api/trading/mt5bridge/...`.
Status koneksi untuk UI: gunakan `status.connected`
(`BRIDGE_DISCONNECTED` / `BRIDGE_DISABLED` / `BRIDGE_TIMEOUT` /
`BRIDGE_COMMAND` untuk pesan error yang jelas).

## Pengujian

```bash
cd backend
python -m pytest tests -q          # 52 test (38 lama + 14 bridge)
```

- **Simulasi (yang dijalankan di repo ini)**: `MockEA` meniru EA lewat TCP
  sungguhan — status, account, price, candles, positions, validasi input,
  EA membalas error, endpoint lama tetap jalan, dan **jaminan tidak ada
  perintah TRADE/CLOSE_POSITION yang pernah mencapai kabel**.
- **Verifikasi rantai nyata tanpa Windows**: jalankan backend dengan
  `MT5_BRIDGE_ENABLED=1`, lalu `python mt5_bridge/mock_ea.py` — semua
  endpoint mengembalikan data contoh. Cocok untuk cek kabel sebelum
  punya VPS/Windows.
- **Live (butuh terminal MT5 + akun nyata)**: pasang EA per bagian A,
  cek log backend "MT5 EA connected", lalu panggil endpoint. Belum bisa
  diuji di lingkungan pengembangan Linux ini — dianggap belum terverifikasi
  sampai kamu menjalankannya.

## Keamanan

- Read-only dua lapis: override metode order + penolakan
  `Action.TRADE/CLOSE_POSITION` di `_send_command`; ada test khusus yang
  membuktikan tidak ada perintah order yang lewat.
- Tidak ada kredensial akun di kode/log/APK — EA hanya membaca terminal
  yang sudah login; backend tidak menyimpan apa pun dari bridge.
- Default bind `127.0.0.1`. Untuk lintas mesin (EA di VPS, backend di
  Termux/PC lain): jangan pernah membuka port ke internet publik mentah.
  Pakai salah satu: (1) LAN dengan firewall whitelist IP, (2) SSH tunnel
  `ssh -R 1111:127.0.0.1:1111 vps` agar EA menyambung ke localhost VPS,
  (3) VPN/WireGuard. Protokol sumber belum punya autentikasi — perlindungan
  jaringan adalah tanggung jawab deployment.

## Keterbatasan & kompatibilitas

- Protokol sumber tidak mengirim nama server/jenis akun/mata uang akun
  (lihat `note` pada endpoint account).
- EA memakai DLL Winsock → hanya Windows/Wine. Android/Termux hanya untuk
  sisi backend/bridge.
- Satu koneksi EA per bridge (desain sumber). Jalankan satu backend bila
  butuh lebih dari satu terminal.
- Candle berformat waktu string broker; volume = tick volume.
- Databridge tidak menulis apa pun ke terminal; semua perintah baca.

## Troubleshooting

| Gejala | Penyebab umum | Solusi |
|---|---|---|
| `BRIDGE_DISABLED` | env belum diset | `MT5_BRIDGE_ENABLED=1` lalu restart backend |
| `BRIDGE_DISCONNECTED` | EA belum jalan / IP-port salah / firewall | cek log backend "MT5 EA connected"; cek `ServerAddress` di EA; buka port |
| `BRIDGE_TIMEOUT` | jaringan lambat / EA sibuk | naikkan `TimerIntervalMs`; cek koneksi VPS |
| `BRIDGE_COMMAND: Invalid symbol` | nama simbol beda antar broker | coba `XAUUSDm`, `GOLD`, atau cek Market Watch |
| EA error saat dipasang | DLL diblokir | centang *Allow DLL imports* saat pasang EA |
| Port bentrok saat start | 1111 dipakai proses lain | ganti `MT5_BRIDGE_PORT` + `ServerPort` EA |
