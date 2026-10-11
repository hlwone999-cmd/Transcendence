/* Akun Trading — mode TANPA BACKEND (murni di browser).
   trading-direct.js: port statistik dari backend/services/stats.py dan
   generator demo dari backend/connectors/demo.py, plus sumber data lokal.
   File ini tidak menyentuh kalkulator (script.js) sama sekali. */
"use strict";

/* ---------------- periode (port resolve_period) ---------------- */
function resolvePeriod(period, fromTs, toTs, nowTs) {
  const now = (nowTs === null || nowTs === undefined)
    ? Math.floor(Date.now() / 1000) : Math.floor(+nowTs);
  const P = ["today", "7d", "30d", "all", "custom"];
  if (P.indexOf(period) < 0) throw new Error("Periode tidak dikenal: " + period);
  if (period === "today") {
    const d = new Date(now * 1000);
    const start = Math.floor(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) / 1000);
    return [start, now];
  }
  if (period === "7d") return [now - 7 * 86400, now];
  if (period === "30d") return [now - 30 * 86400, now];
  if (period === "all") return [0, now];
  fromTs = Math.floor(+fromTs || 0); toTs = Math.floor(+toTs || 0);
  if (fromTs <= 0 || toTs <= 0 || fromTs > toTs)
    throw new Error("Rentang tanggal khusus tidak valid.");
  return [fromTs, Math.min(toTs, now)];
}

/* ---------------- statistik (port compute_summary) ---------------- */
function netPL(d) {
  return (+d.profit || 0) + (+d.swap || 0) + (+d.commission || 0);
}
function filterDeals(deals, since, until) {
  return (deals || []).filter(d =>
    d.close_time !== null && d.close_time !== undefined &&
    since <= d.close_time && d.close_time <= until);
}
function r2(v) { return Math.round(v * 100) / 100; }

function equityAndDrawdown(deals, deposits) {
  const ev = (deposits || []).map(o => ({ t: o.time, amt: +o.amount }))
    .concat((deals || []).map(d => ({ t: d.close_time, amt: netPL(d) })))
    .filter(e => e.t !== null && e.t !== undefined)
    .sort((a, b) => a.t - b.t);
  if (!ev.length) return [[], null, null];
  let eq = 0, peak = null, ddP = 0, ddA = 0;
  const pts = [];
  for (const e of ev) {
    eq += e.amt;
    peak = (peak === null) ? eq : Math.max(peak, eq);
    const ddAbs = peak - eq;
    const ddPct = peak > 0 ? ddAbs / peak * 100 : 0;
    if (ddPct >= ddP) { ddP = ddPct; ddA = ddAbs; }
    pts.push({ t: e.t, balance: r2(eq) });
  }
  return [pts, (ddP || null), (ddA || null)];
}

function equityCurve(deals, deposits) {
  return equityAndDrawdown(deals, deposits)[0];
}

function computeSummary(deals, deposits, floating, balance, equity) {
  deposits = deposits || [];
  floating = +floating || 0;
  const nets = (deals || []).map(netPL);
  const wins = nets.filter(n => n > 0), losses = nets.filter(n => n < 0);
  const be = nets.length - wins.length - losses.length;
  const grossWin = wins.reduce((a, b) => a + b, 0);
  const grossLoss = Math.abs(losses.reduce((a, b) => a + b, 0));
  const denom = wins.length + losses.length;
  const hasDeps = deposits.length > 0;
  const totalDep = hasDeps
    ? deposits.filter(o => o.amount > 0).reduce((a, o) => a + o.amount, 0) : null;
  const totalWd = hasDeps
    ? Math.abs(deposits.filter(o => o.amount < 0).reduce((a, o) => a + o.amount, 0)) : null;
  const dd = equityAndDrawdown(deals, deposits);
  const pf = grossLoss > 0 ? r2(grossWin / grossLoss)
    : (grossWin === 0 ? null : "inf");
  return {
    balance: balance, equity: equity, floating: r2(floating),
    total_deals: nets.length,
    wins: wins.length, losses: losses.length, breakeven: be,
    win_rate: denom ? r2(wins.length / denom * 100) : null,
    gross_profit: r2(grossWin), gross_loss: r2(grossLoss),
    net_profit: r2(grossWin - grossLoss),
    avg_win: wins.length ? r2(grossWin / wins.length) : null,
    avg_loss: losses.length ? r2(grossLoss / losses.length) : null,
    profit_factor: pf,
    total_deposit: totalDep === null ? null : r2(totalDep),
    total_withdrawal: totalWd === null ? null : r2(totalWd),
    max_drawdown_pct: dd[1], max_drawdown_abs: dd[2],
    best_trade: nets.length ? r2(Math.max.apply(null, nets)) : null,
    worst_trade: nets.length ? r2(Math.min.apply(null, nets)) : null,
    deposits_available: hasDeps
  };
}

/* ---------------- demo (port connectors/demo.py) ---------------- */
function demoGenerate(seed, nowTs) {
  const now = (nowTs === null || nowTs === undefined)
    ? Math.floor(Date.now() / 1000) : Math.floor(+nowTs);
  // PRNG deterministik dari string seed (xorshift32 + FNV-1a)
  let h = 2166136261 >>> 0;
  const s = "txdemo::" + String(seed);
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  let st = h || 1;
  const rnd = () => {
    st = (st + 0x6D2B79F5) | 0;
    let z = Math.imul(st ^ (st >>> 15), 1 | st);
    z = (z + Math.imul(z ^ (z >>> 7), 61 | z)) ^ z;
    return ((z ^ (z >>> 14)) >>> 0) / 4294967296;
  };
  const uni = (a, b) => a + rnd() * (b - a);
  const pick = arr => arr[Math.floor(rnd() * arr.length)];

  const INIT = 10000.0, SYMBOLS = ["XAUUSD", "EURUSD", "BTCUSD"];
  const start = now - 60 * 86400;
  const ops = [{ time: start, type: "deposit", amount: INIT }];
  const closed = [];
  let t = start + 3600, ticket = 100000;
  for (let i = 0; i < 140; i++) {
    if (i === 40 || i === 90) {
      const amt = i === 40 ? 2000 : -1500;
      ops.push({ time: Math.floor(t), type: amt > 0 ? "deposit" : "withdrawal", amount: amt });
    }
    const sym = pick(SYMBOLS);
    const isWin = rnd() < 0.56;
    const risk = uni(0.008, 0.015) * INIT;
    const profit = r2(isWin ? risk * uni(1.2, 2.4) : -risk * uni(0.8, 1.05));
    const hold = Math.floor(uni(20, 301)) * 60;
    closed.push({
      ticket: ticket, symbol: sym, type: pick(["buy", "sell"]),
      volume: r2(uni(0.05, 1.2)),
      open_price: r2(uni(1800, 2700)), close_price: r2(uni(1800, 2700)),
      open_time: Math.floor(t), close_time: Math.floor(t + hold),
      profit: profit, swap: r2(uni(-0.4, 0.4)),
      commission: r2(-Math.abs(uni(0, 0.8)))
    });
    ticket += 7;
    t += hold + Math.floor(uni(30, 401)) * 60;
    if (t > now - 3600) break;
  }
  const openPos = [];
  for (let k = 0; k < 3; k++) {
    openPos.push({
      ticket: ticket + k, symbol: SYMBOLS[k % SYMBOLS.length],
      type: pick(["buy", "sell"]), volume: r2(uni(0.05, 0.6)),
      open_price: r2(uni(1800, 2700)),
      open_time: now - Math.floor(uni(1, 21)) * 3600,
      close_time: null,
      profit: r2(uni(-180, 240)), swap: r2(uni(-0.3, 0.3)), commission: -0.5
    });
  }
  const balance = INIT + ops.reduce((a, o) => a + o.amount, 0)
    + closed.reduce((a, c) => a + c.profit + c.swap + c.commission, 0);
  const floating = r2(openPos.reduce((a, p) => a + p.profit + p.swap + p.commission, 0));
  return {
    ops: ops, closed: closed, openPos: openPos,
    info: {
      login: String(seed), name: "Akun Demonstrasi",
      broker: "DEMO — bukan akun sungguhan", server: "demo-server",
      currency: "USD", leverage: 500, platform: "demo",
      balance: r2(balance), equity: r2(balance + floating)
    }
  };
}

/* ---------------- sumber data lokal (tanpa backend) ---------------- */
/* snapshot(): info akun untuk status bar; dashboard(period, from, to):
   {summary, hist, curve} — bentuk identik dengan respons API backend. */
function makeLocalSource(cfg) {
  function dataset() {
    return typeof cfg.data === "function" ? cfg.data() : cfg.data;
  }
  function snapshot() {
    const d = dataset();
    return {
      connected: true, mode: cfg.mode, platform: cfg.platform,
      label: cfg.label || (d.info && (d.info.login || cfg.mode)) || cfg.mode,
      account: d.info
    };
  }
  function dashboard(period, fromVal, toVal) {
    const d = dataset();
    const [since, until] = resolvePeriod(period,
      period === "custom" ? customTs(fromVal, false) : 0,
      period === "custom" ? customTs(toVal, true) : 0);
    const deals = filterDeals(d.closed, since, until);
    const deps = (d.ops || []).filter(o => since <= o.time && o.time <= until);
    const floating = cfg.floating !== undefined ? cfg.floating
      : r2((d.openPos || []).reduce((a, p) => a + (+p.profit || 0) + (+p.swap || 0) + (+p.commission || 0), 0));
    const balance = d.info.balance, equity = d.info.equity;
    const summary = computeSummary(deals, deps.length ? deps : null, floating, balance, equity);
    summary.period = period; summary.mode = cfg.mode;
    summary.notes = cfg.notes || [
      "Statistik dihitung langsung di browser tanpa backend.",
      "Profit bersih = profit + swap + komisi per posisi tertutup.",
      "Drawdown dihitung dari kurva balance trade tertutup, bukan tick-per-tick."
    ];
    const histDeals = deals.slice().sort((a, b) => (b.close_time || 0) - (a.close_time || 0));
    return {
      summary: summary,
      hist: { total: deals.length, deals: histDeals.slice(0, 100), mode: cfg.mode, period: period },
      curve: { points: equityCurve(deals, deps), mode: cfg.mode, period: period }
    };
  }
  return { backend: false, mode: cfg.mode, platform: cfg.platform,
           snapshot: snapshot, dashboard: dashboard };
}

function customTs(val, endOfDay) {
  if (!val) return endOfDay ? Math.floor(Date.now() / 1000) : 0;
  const t = Date.parse(val + (endOfDay ? "T23:59:59Z" : "T00:00:00Z")) / 1000;
  return Math.floor(t || 0);
}

const Sources = {
  demo: function (seed) {
    const s = seed || ("demo-" + Math.random().toString(36).slice(2, 6));
    return makeLocalSource({
      mode: "demo", platform: "demo", label: "DEMO",
      data: () => demoGenerate(s),
      notes: [
        "MODE DEMONSTRASI — data contoh dibangkitkan acak-di browser, bukan akun sungguhan.",
        "Profit bersih = profit + swap + komisi per posisi tertutup."
      ]
    });
  },
  imported: function (ds) {
    const meta = (ds && ds.meta) || {};
    const info = {
      login: meta.login || "-", name: meta.name || "Data impor",
      broker: meta.broker || "dari laporan", server: meta.server || "-",
      currency: meta.currency || "USD", leverage: meta.leverage || null,
      platform: "import"
    };
    // balance untuk data impor: kolom Balance terakhir, atau deposit + net P/L
    let bal = null;
    if (ds.balances && ds.balances.length) {
      bal = ds.balances[ds.balances.length - 1].balance;
    } else if (ds.deposits && ds.deposits.length) {
      bal = r2(ds.deposits.reduce((a, o) => a + o.amount, 0)
        + (ds.deals || []).reduce((a, c) => a + netPL(c), 0));
    }
    if (bal !== null && bal !== undefined && isFinite(+bal)) {
      info.balance = r2(+bal); info.equity = r2(+bal);
    } else { info.balance = null; info.equity = null; }
    return makeLocalSource({
      mode: "import", platform: "import", label: "Data impor",
      data: { info: info, closed: ds.deals || [], ops: ds.deposits || [], openPos: [] },
      floating: 0,
      notes: [
        "Data dihitung di browser dari laporan yang diimpor — tidak ada koneksi ke broker.",
        "Posisi terbuka & floating P/L tidak tersedia pada data impor.",
        "Profit bersih = profit + swap + komisi per posisi tertutup."
      ]
    });
  },
  backend: function () { return { backend: true, mode: "backend" }; }
};
