/* Akun Trading — IMPOR LAPORAN (mode tanpa backend, murni browser).
   trading-import.js: parser file laporan MT4/MT5 (HTML / CSV) + file JSON
   hasil skrip ekspor (mt-export/), plus penyimpanan lokal (localStorage).
   Tidak menyentuh kalkulator (script.js). */
"use strict";

/* ---------------- util angka & waktu ---------------- */
function pnum(s) {
  s = String(s == null ? "" : s).replace(/[\s\u00a0]/g, "");
  if (!s) return NaN;
  const neg = s[0] === "-" || (/^\(.*\)$/.test(s));
  s = s.replace(/[-+()]/g, "");
  const hasC = s.indexOf(",") >= 0, hasD = s.indexOf(".") >= 0;
  if (hasC && hasD) {
    s = (s.lastIndexOf(",") > s.lastIndexOf("."))
      ? s.replace(/\./g, "").replace(",", ".")
      : s.replace(/,/g, "");
  } else if (hasC) {
    s = (/,\d{1,2}$/.test(s)) ? s.replace(",", ".") : s.replace(/,/g, "");
  } else if (hasD) {
    if (s.split(".").length > 2 || (/\.\d{3}(\.|$)/.test(s) && s.length > 6))
      s = s.replace(/\./g, "");
  }
  const v = parseFloat(s);
  return neg ? -v : v;
}

function pts(s) {
  const m = String(s == null ? "" : s).trim()
    .match(/(\d{4})[.\/\-](\d{1,2})[.\/\-](\d{1,2})[ T]*(\d{1,2})?:?(\d{1,2})?:?(\d{1,2})?/);
  if (!m) return null;
  return Math.floor(Date.UTC(+m[1], +m[2] - 1, +m[3],
    +(m[4] || 0), +(m[5] || 0), +(m[6] || 0)) / 1000);
}

function decodeEntities(s) {
  return String(s == null ? "" : s)
    .replace(/&#(\d+);/g, (m, d) => String.fromCharCode(+d))
    .replace(/&nbsp;/gi, " ").replace(/&amp;/gi, "&").replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">").replace(/&quot;/gi, '"').replace(/&#39;/gi, "'");
}

/* ---------------- deteksi kolom lewat header (EN/ID) ---------------- */
const HDR = {
  close: [/close\s*time/i, /waktu\s*penutup/i, /^penutupan/i],
  time: [/^time$/i, /^waktu$/i, /open\s*time/i, /^tanggal/i, /open\s*date/i],
  ticket: [/^ticket$/i, /^tiket$/i, /^deal$/i, /^position$/i, /^posisi$/i],
  type: [/^type$/i, /^tipe$/i, /^jenis$/i, /^action$/i],
  dir: [/direction/i, /arah/i, /^entry$/i],
  symbol: [/symbol/i, /simbol/i, /^item$/i],
  volume: [/volume/i, /^size$/i, /^lots?$/i],
  openp: [/open\s*price/i, /harga\s*buka/i],
  closep: [/close\s*price/i, /harga\s*penutup/i],
  profit: [/^profit$/i, /^laba/i, /^untung/i, /^net$/i],
  comm: [/commission/i, /komisi/i, /^fee$/i],
  tax: [/tax/i, /pajak/i],
  swap: [/swap/i],
  balance: [/^balance$/i, /^saldo$/i]
};

function mapHeader(cells) {
  const idx = {};
  let hits = 0;
  for (let i = 0; i < cells.length; i++) {
    const c = cells[i].trim();
    for (const key in HDR) {
      if (idx[key] === undefined && HDR[key].some(rx => rx.test(c))) {
        idx[key] = i; hits++;
      }
    }
  }
  if (hits >= 3 && idx.time !== undefined && idx.profit !== undefined) return idx;
  return null;
}

function headerIdx(rows) {
  for (const r of rows) {
    const idx = mapHeader(r.cells);
    if (idx) return { idx, headerRow: r };
  }
  return null;
}

/* ---------------- klasifikasi baris ---------------- */
function classifyRow(cells, idx) {
  let type = idx && idx.type !== undefined ? cells[idx.type] : "";
  if (!type) {
    for (const c of cells) {
      if (/^(buy|sell|beli|jual|balance|saldo|deposit|withdraw)/i.test(c.trim())) {
        type = c.trim(); break;
      }
    }
  }
  return String(type || "").trim();
}

function rowsToData(rows, base) {
  const out = base || { deals: [], deposits: [], balances: [] };
  const h = headerIdx(rows);
  const idx = h ? h.idx : null;
  for (const r of rows) {
    const cells = r.cells;
    const type = classifyRow(cells, idx);
    if (!type) continue;
    const get = k => (idx && idx[k] !== undefined && cells[idx[k]] !== undefined)
      ? cells[idx[k]] : "";
    const t0 = pts(idx && idx.time !== undefined ? get("time")
      : cells.find(c => pts(c) !== null) || "");
    if (t0 === null) continue;
    if (/^(balance|saldo|deposit|withdraw)/i.test(type)) {
      const amt = pnum(get("profit") || (idx ? "" : cells[cells.length - 2]));
      if (isFinite(amt) && amt !== 0)
        out.deposits.push({ time: t0, type: amt > 0 ? "deposit" : "withdrawal", amount: r2(amt) });
      continue;
    }
    if (!/^(buy|sell|beli|jual)/i.test(type)) continue;
    const dir = get("dir");
    if (dir && !/out|keluar/i.test(dir)) continue;          // deal IN = pembukaan
    const closeT = idx && idx.close !== undefined ? pts(get("close")) : t0;
    if (!closeT) continue;                                   // posisi terbuka
    const comm = (pnum(get("comm")) || 0) + (pnum(get("tax")) || 0);
    out.deals.push({
      ticket: get("ticket") || "",
      symbol: (get("symbol") || "").trim(),
      type: /buy|beli/i.test(type) ? "buy" : "sell",
      volume: pnum(get("volume")) || 0,
      open_time: t0, close_time: closeT,
      open_price: pnum(get("openp")) || null,
      close_price: pnum(get("closep")) || null,
      profit: pnum(get("profit")) || 0,
      swap: pnum(get("swap")) || 0,
      commission: r2(comm)
    });
    const bal = pnum(get("balance"));
    if (isFinite(bal) && bal !== 0) out.balances.push({ t: closeT, balance: bal });
  }
  out.deals.sort((a, b) => a.close_time - b.close_time);
  out.balances.sort((a, b) => a.t - b.t);
  return out;
}

/* ---------------- laporan HTML (MT5 report / MT4 statement) ---------------- */
function htmlRows(html) {
  const clean = html.replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ");
  const rows = [];
  const reRow = /<tr[^>]*>([\s\S]*?)<\/tr>/gi;
  let m;
  while ((m = reRow.exec(clean)) !== null) {
    const cells = [];
    const reCell = /<t[dh][^>]*>([\s\S]*?)<\/t[dh]/gi;
    let c;
    while ((c = reCell.exec(m[1])) !== null) {
      cells.push(decodeEntities(c[1].replace(/<[^>]*>/g, " ").trim()));
    }
    if (cells.length) rows.push({ cells: cells });
  }
  return rows;
}

function extractMeta(text) {
  const meta = {};
  const flat = decodeEntities(String(text).replace(/<[^>]*>/g, " ")).replace(/\s+/g, " ");
  const grab = (rx) => {
    const m = flat.match(rx);
    return m ? m[1].trim() : "";
  };
  meta.login = grab(/login\W{0,4}(\d{4,12})\b/i);
  meta.name = grab(/\bname\W{0,3}([A-Za-z .'-]{2,40}?)(?=\s+[A-Z][A-Za-z]{0,14}:|\(|$)/i);
  meta.server = grab(/server\W{0,3}([A-Za-z0-9 ._\-]{3,40}?)(?=\s+[A-Z][A-Za-z]{0,14}:|\(|$)/i);
  meta.broker = grab(/broker\W{0,3}([A-Za-z0-9 .,'&\-]{3,50}?)(?=\s+[A-Z][A-Za-z]{0,14}:|\s+Deposit\b|\s+Withdrawal\b|\(|$)/i);
  meta.currency = grab(/(?:deposit\s*)?currency\W{0,3}(USD|EUR|IDR|SGD|AUD|GBP|JPY|CAD|CHF|NZD|MYR)\b/i);
  if (!meta.currency) meta.currency = "USD";
  for (const k in meta) if (!meta[k]) delete meta[k];
  return meta;
}

function parseHTMLReport(html) {
  const rows = htmlRows(html);
  if (!rows.length) throw new Error("Tidak ada tabel yang bisa dibaca di file HTML ini.");
  const out = rowsToData(rows, { deals: [], deposits: [], balances: [] });
  if (!out.deposits.length && out.deals.length) {
    // MT4 statement: deposit/withdrawal hanya muncul di bagian Summary
    const flat = decodeEntities(html.replace(/<[^>]*>/g, " ")).replace(/\s+/g, " ");
    const m = flat.match(/deposit\s*[\/\\]?\s*withdrawal\W{0,40}(-?[\d.,\s]+)/i);
    const amt = m ? pnum(m[1]) : NaN;
    if (isFinite(amt) && amt !== 0) {
      out.deposits.push({ time: out.deals[0].close_time,
        type: amt > 0 ? "deposit" : "withdrawal", amount: amt });
    }
  }
  finish(out, html);
  return out;
}

/* ---------------- CSV ---------------- */
function parseCSV(text) {
  const lines = String(text).split(/\r?\n/).filter(l => l.trim());
  if (!lines.length) throw new Error("File CSV kosong.");
  const head = lines[0];
  const delim = ["\t", ";", ","].sort((a, b) =>
    head.split(b).length - head.split(a).length)[0];
  const rows = lines.map(l => {
    const cells = l.split(delim).map(s => decodeEntities(s.trim()));
    return { cells: cells };
  });
  const out = rowsToData(rows, { deals: [], deposits: [], balances: [] });
  finish(out, text);
  return out;
}

/* ---------------- JSON hasil skrip ekspor (mt-export/) ---------------- */
function parseExportJSON(text) {
  let d;
  try { d = JSON.parse(text); }
  catch (e) { throw new Error("File JSON tidak valid."); }
  if (!d || String(d.schema || "").indexOf("kalkulator-xauusd/trading-export") !== 0)
    throw new Error("JSON ini bukan hasil skrip ekspor Kalkulator XAUUSD (schema tidak dikenal).");
  const out = {
    meta: {},
    deals: (d.deals || []).map(x => ({
      ticket: x.ticket, symbol: x.symbol,
      type: x.type === "sell" ? "sell" : "buy",
      volume: +x.volume || 0,
      open_time: x.open_time || null, close_time: x.close_time,
      open_price: x.open_price || null, close_price: x.close_price || null,
      profit: +x.profit || 0, swap: +x.swap || 0, commission: +x.commission || 0
    })),
    deposits: (d.balance_operations || []).map(x => ({
      time: +x.time, type: (+x.amount) > 0 ? "deposit" : "withdrawal",
      amount: +x.amount
    })),
    balances: []
  };
  if (d.account) out.meta = {
    login: String(d.account.login || ""), name: d.account.name || "",
    broker: d.account.broker || "", server: d.account.server || "",
    currency: d.account.currency || "USD", leverage: d.account.leverage || null
  };
  finish(out, "");
  return out;
}

/* ---------------- validasi akhir ---------------- */
function r2(v) { return Math.round(v * 100) / 100; }

function finish(out, rawText) {
  out.deals.forEach(d => {
    d.volume = r2(+d.volume || 0);
    d.profit = r2(+d.profit || 0);
    d.swap = r2(+d.swap || 0);
    d.commission = r2(+d.commission || 0);
  });
  out.deposits.sort((a, b) => a.time - b.time);
  if (!out.deals.length && !out.deposits.length) {
    throw new Error("Tidak menemukan transaksi di file ini. Gunakan laporan resmi "
      + "MT4/MT5 (Account History → Save as Report), CSV dengan kolom waktu/"
      + "tipe/volume/profit, atau file JSON dari skrip ekspor (mt-export/).");
  }
  if (rawText && !out.meta || (rawText && Object.keys(out.meta || {}).length === 0)) {
    out.meta = Object.assign(extractMeta(rawText), out.meta || {});
  }
}

/* ---------------- pintu masuk ---------------- */
function parseReport(text, fileName) {
  const t = String(text).replace(/^\uFEFF/, "");
  let out;
  if (/^\s*[\[{]/.test(t)) out = parseExportJSON(t);
  else if (/<tr[\s>]|<table/i.test(t)) out = parseHTMLReport(t);
  else out = parseCSV(t);
  out.file_name = fileName || "";
  return out;
}

/* ---------------- penyimpanan lokal (localStorage) ---------------- */
const IMPORT_KEY = "tx_import_v1";
const LS_OK = (function () {
  try { return typeof localStorage !== "undefined" && !!localStorage; }
  catch (e) { return false; }
})();

function saveImported(ds, fileName) {
  if (!LS_OK) return { saved: false, reason: "Browser tidak mengizinkan localStorage." };
  try {
    localStorage.setItem(IMPORT_KEY, JSON.stringify({
      schema: 1, saved_at: Math.floor(Date.now() / 1000),
      file_name: fileName || "", meta: ds.meta,
      deals: ds.deals, deposits: ds.deposits, balances: ds.balances || []
    }));
    return { saved: true };
  } catch (e) {
    return { saved: false,
      reason: "Data terlalu besar untuk disimpan di browser — impor tetap dipakai, tapi tidak tersisa setelah halaman ditutup." };
  }
}

function loadImported() {
  if (!LS_OK) return null;
  try {
    const raw = localStorage.getItem(IMPORT_KEY);
    if (!raw) return null;
    const d = JSON.parse(raw);
    if (!d || d.schema !== 1 || !(d.deals || []).length) return null;
    return { meta: d.meta || {}, deals: d.deals, deposits: d.deposits || [],
      balances: d.balances || [], file_name: d.file_name || "" };
  } catch (e) { return null; }
}

function clearImported() {
  if (LS_OK) { try { localStorage.removeItem(IMPORT_KEY); } catch (e) { } }
}
