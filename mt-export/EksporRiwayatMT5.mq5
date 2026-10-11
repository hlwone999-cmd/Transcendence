//+------------------------------------------------------------------+
//| EksporRiwayatMT5.mq5                                             |
//| Ekspor riwayat akun MT5 ke JSON untuk dashboard Kalkulator XAUUSD|
//| READ-ONLY: hanya membaca riwayat & info akun. Tidak ada order.   |
//| Hasil: MQL5\Files\trading-export-<login>.json                    |
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
      ushort c = StringGetCharacter(s, i);
      if (c == '"' || c == '\\') { out += "\\"; out += CharToString((uchar)c); }
      else if (c >= 32 && c < 127) out += CharToString((uchar)c);
      else out += "?";
   }
   if (out == "") out = "-";
   return out;
}
string JStr(string k, string v) { return "\"" + k + "\":\"" + Ascii(v) + "\""; }
string JNum(string k, double v, int dig) { return "\"" + k + "\":" + DoubleToString(v, dig); }
string JInt(string k, long v) { return "\"" + k + "\":" + IntegerToString(v); }

//+------------------------------------------------------------------+
void OnStart() {
   if (!HistorySelect(0, TimeCurrent() + 86400)) {
      Print("Gagal membaca riwayat: ", GetLastError());
      return;
   }
   int total = HistoryDealsTotal();
   string json = "{";
   json += "\"schema\":\"kalkulator-xauusd/trading-export@1\",";
   json += JInt("generated_at", (long)TimeCurrent()) + ",";
   json += "\"platform\":\"mt5\",";
   json += "\"account\":{";
   json += JStr("login", IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))) + ",";
   json += JStr("name", AccountInfoString(ACCOUNT_NAME)) + ",";
   json += JStr("broker", AccountInfoString(ACCOUNT_COMPANY)) + ",";
   json += JStr("server", AccountInfoString(ACCOUNT_SERVER)) + ",";
   json += JStr("currency", AccountInfoString(ACCOUNT_CURRENCY)) + ",";
   json += JInt("leverage", AccountInfoInteger(ACCOUNT_LEVERAGE)) + ",";
   json += JNum("balance", AccountInfoDouble(ACCOUNT_BALANCE), 2);
   json += "},";
   json += "\"deals\":[";
   int nd = 0, nops = 0;
   string opsJson = "";
   for (int i = 0; i < total; i++) {
      ulong tk = HistoryDealGetTicket(i);
      if (tk == 0) continue;
      long dtype = HistoryDealGetInteger(tk, DEAL_TYPE);
      long dentry = HistoryDealGetInteger(tk, DEAL_ENTRY);
      if (dtype == DEAL_TYPE_BALANCE) {
         double amt = HistoryDealGetDouble(tk, DEAL_PROFIT);
         if (amt == 0) continue;
         if (nops > 0) opsJson += ",";
         opsJson += "{";
         opsJson += JInt("time", HistoryDealGetInteger(tk, DEAL_TIME)) + ",";
         opsJson += JStr("type", amt > 0 ? "deposit" : "withdrawal") + ",";
         opsJson += JNum("amount", amt, 2);
         opsJson += "}";
         nops++;
         continue;
      }
      bool isTrade = (dtype == DEAL_TYPE_BUY || dtype == DEAL_TYPE_SELL);
      bool isClosed = (dentry == DEAL_ENTRY_OUT || dentry == DEAL_ENTRY_INOUT
                       || dentry == DEAL_ENTRY_OUT_BY);
      if (!isTrade || !isClosed) continue;
      if (nd > 0) json += ",";
      json += "{";
      json += JInt("ticket", (long)tk) + ",";
      json += JStr("symbol", HistoryDealGetString(tk, DEAL_SYMBOL)) + ",";
      json += JStr("type", dtype == DEAL_TYPE_BUY ? "buy" : "sell") + ",";
      json += JNum("volume", HistoryDealGetDouble(tk, DEAL_VOLUME), 2) + ",";
      json += JNum("open_price", HistoryDealGetDouble(tk, DEAL_PRICE), 5) + ",";
      json += JInt("open_time", 0) + ",";
      json += JInt("close_time", HistoryDealGetInteger(tk, DEAL_TIME)) + ",";
      json += JNum("profit", HistoryDealGetDouble(tk, DEAL_PROFIT), 2) + ",";
      json += JNum("swap", HistoryDealGetDouble(tk, DEAL_SWAP), 2) + ",";
      json += JNum("commission", HistoryDealGetDouble(tk, DEAL_COMMISSION), 2);
      json += "}";
      nd++;
   }
   json += "],";
   json += "\"balance_operations\":[" + opsJson + "]}";

   string fname = (InpFileName == "")
      ? "trading-export-" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ".json"
      : InpFileName;
   int h = FileOpen(fname, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if (h == INVALID_HANDLE) {
      Print("Gagal membuat file (error ", GetLastError(), "). Coba isi InpFileName manual.");
      return;
   }
   FileWriteString(h, json);
   FileClose(h);
   string path = TerminalInfoString(TERMINAL_DATA_PATH) + "\\MQL5\\Files\\" + fname;
   Print("=== EKSPOR SELESAI (read-only, tanpa order) ===");
   Print("Transaksi tertutup: ", nd, " | Operasi balance: ", nops);
   Print("File: ", path);
   Print("Buka file tsb, lalu impor di trading.html -> kartu 'Impor laporan'.");
   Alert("Ekspor selesai: ", nd, " transaksi. File ada di folder MQL5\\Files.");
}
//+------------------------------------------------------------------+
