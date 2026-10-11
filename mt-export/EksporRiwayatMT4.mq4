//+------------------------------------------------------------------+
//| EksporRiwayatMT4.mq4                                             |
//| Ekspor riwayat akun MT4 ke JSON untuk dashboard Kalkulator XAUUSD|
//| READ-ONLY: hanya membaca riwayat & info akun. Tidak ada order.   |
//| Hasil: MQL4\Files\trading-export-<login>.json                    |
//+------------------------------------------------------------------+
#property copyright "kalkulator-xauusd"
#property link        "https://github.com/hlwone999-cmd/kalkulator-xauusd"
#property version     "1.00"
#property script_show_inputs
input string InpFileName = "";   // Nama file output (kosong = otomatis)

//+------------------------------------------------------------------+
string Ascii(string s) {
   string out = "";
   for (int i = 0; i < StringLen(s); i++) {
      int c = StringGetChar(s, i);
      if (c == '"' || c == '\\') { out += "\\"; out += CharToString((uchar)c); }
      else if (c >= 32 && c < 127) out += CharToString((uchar)c);
      else out += "?";
   }
   if (out == "") out = "-";
   return out;
}
string JStr(string k, string v) { return "\"" + k + "\":\"" + Ascii(v) + "\""; }
string JNum(string k, double v, int dig) { return "\"" + k + "\":" + DoubleToString(v, dig); }
string JInt(string k, int v) { return "\"" + k + "\":" + IntegerToString(v); }

//+------------------------------------------------------------------+
void OnStart() {
   string json = "{";
   json += "\"schema\":\"kalkulator-xauusd/trading-export@1\",";
   json += JInt("generated_at", (int)TimeCurrent()) + ",";
   json += "\"platform\":\"mt4\",";
   json += "\"account\":{";
   json += JStr("login", IntegerToString(AccountNumber())) + ",";
   json += JStr("name", AccountName()) + ",";
   json += JStr("broker", AccountCompany()) + ",";
   json += JStr("server", AccountServer()) + ",";
   json += JStr("currency", AccountCurrency()) + ",";
   json += JInt("leverage", AccountLeverage()) + ",";
   json += JNum("balance", AccountBalance(), 2);
   json += "},";
   json += "\"deals\":[";
   int n = OrdersHistoryTotal();
   int nd = 0, nops = 0;
   string opsJson = "";
   for (int i = 0; i < n; i++) {
      if (!OrderSelect(i, SELECT_BY_POS, MODE_HISTORY)) continue;
      int ot = OrderType();
      double amt = OrderProfit();
      if (ot == OP_BALANCE) {
         if (amt == 0) continue;
         if (nops > 0) opsJson += ",";
         opsJson += "{";
         opsJson += JInt("time", OrderOpenTime()) + ",";
         opsJson += JStr("type", amt > 0 ? "deposit" : "withdrawal") + ",";
         opsJson += JNum("amount", amt, 2);
         opsJson += "}";
         nops++;
         continue;
      }
      if (ot != OP_BUY && ot != OP_SELL) continue;   // pending terhapus: lewati
      if (OrderCloseTime() <= 0) continue;           // belum tertutup: lewati
      if (nd > 0) json += ",";
      json += "{";
      json += JInt("ticket", OrderTicket()) + ",";
      json += JStr("symbol", OrderSymbol()) + ",";
      json += JStr("type", ot == OP_BUY ? "buy" : "sell") + ",";
      json += JNum("volume", OrderLots(), 2) + ",";
      json += JNum("open_price", OrderOpenPrice(), 5) + ",";
      json += JInt("open_time", OrderOpenTime()) + ",";
      json += JInt("close_time", OrderCloseTime()) + ",";
      json += JNum("close_price", OrderClosePrice(), 5) + ",";
      json += JNum("profit", OrderProfit(), 2) + ",";
      json += JNum("swap", OrderSwap(), 2) + ",";
      json += JNum("commission", OrderCommission(), 2);
      json += "}";
      nd++;
   }
   json += "],";
   json += "\"balance_operations\":[" + opsJson + "]}";

   string fname = (InpFileName == "")
      ? "trading-export-" + IntegerToString(AccountNumber()) + ".json"
      : InpFileName;
   int h = FileOpen(fname, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if (h == INVALID_HANDLE) {
      Print("Gagal membuat file (error ", GetLastError(), "). Coba isi InpFileName manual.");
      return;
   }
   FileWriteString(h, json);
   FileClose(h);
   string path = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL4\\Files\\" + fname;
   Print("=== EKSPOR SELESAI (read-only, tanpa order) ===");
   Print("Transaksi tertutup: ", nd, " | Operasi balance: ", nops);
   Print("File: ", path);
   Print("Buka file tsb, lalu impor di trading.html -> kartu 'Impor laporan'.");
   Alert("Ekspor selesai: ", nd, " transaksi. File ada di folder MQL4\\Files.");
}
//+------------------------------------------------------------------+
