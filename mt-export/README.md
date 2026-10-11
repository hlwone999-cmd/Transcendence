# Skrip Ekspor Riwayat (MT4 & MT5) — mode tanpa backend

Cara paling **akurat** untuk memakai dashboard `trading.html` tanpa Python:
ekspor riwayat akun langsung dari terminal MetaTrader ke file JSON, lalu impor
file-nya di halaman trading. Skrip ini **read-only** — hanya membaca riwayat
dan info akun, tidak bisa dan tidak pernah mengirim order.

## Instalasi (MT5)

1. Buka MetaTrader 5 → menu **File → Open Data Folder** → masuk ke `MQL5\Scripts\`.
2. Salin `EksporRiwayatMT5.mq5` ke situ.
3. Di Navigator MT5 (Ctrl+N), klik kanan **Scripts → Refresh**.
4. Pastikan akun sudah login dan tab **Toolbox → History** memuat riwayat akun.
5. Seret skrip `EksporRiwayatMT5` ke grafik apa saja → dialog muncul → **OK**.
6. Hasil: `MQL5\Files\trading-export-<login>.json` (path lengkap tercetak di tab Experts/Journal).

## Instalasi (MT4)

1. Buka MetaTrader 4 → **File → Open Data Folder** → masuk ke `MQL4\Scripts\`.
2. Salin `EksporRiwayatMT4.mq4` ke situ.
3. Di Navigator, klik kanan **Scripts → Refresh**.
4. Seret `EksporRiwayatMT4` ke grafik → **OK**.
5. Hasil: `MQL4\Files\trading-export-<login>.json`.

## Impor ke dashboard

1. Buka `trading.html` (boleh dari file lokal, Vercel, atau backend).
2. Kartu **Impor laporan (tanpa server)** → **Pilih file laporan…** → pilih
   `trading-export-<login>.json` tadi.
3. Dashboard menghitung semua statistik di browser. Data disimpan di
   localStorage browser (tidak dikirim ke internet), bisa dihapus lewat tombol
   **Hapus data impor**.

## Kenapa lewat JSON, bukan laporan HTML?

Parser HTML laporan bersifat *best-effort* karena format laporan berbeda antar
broker dan bahasa antarmuka. File JSON hasil skrip ini mengikuti schema tetap
`kalkulator-xauusd/trading-export@1`, jadi angka 100% akurat, termasuk
deposit/withdrawal (MT4 sekalipun, yang tidak tersedia lewat bridge PyTrader).

## Keamanan

- Skrip tidak mengirim apa pun ke jaringan (tidak ada WebRequest/socket).
- Password akun tidak disentuh sama sekali.
- File JSON berisi riwayat trading — simpan sesuai keinginanmu; jangan dibagikan
  jika kamu menganggapnya privat.
