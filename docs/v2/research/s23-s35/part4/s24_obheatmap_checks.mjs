// S24 order-book-heatmap checks H2-H3 (rules: PREREGISTERED.md), plus labelled exploratory H4.
// Usage: node s24_obheatmap_checks.mjs /path/to/order-book-heatmap out.json
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const [repo, outPath] = process.argv.slice(2);
const Tick = (await import(pathToFileURL(`${repo}/lib/Tick.js`).href)).default;
const Book = (await import(pathToFileURL(`${repo}/lib/BinanceOrderBook.js`).href)).default;
const out = {};

// deterministic PRNG (mulberry32)
let s = 20261116;
const rnd = () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };

// ---------- H2: string -> tick round trip ----------
for (const [ts, dec] of [['0.01', 2], ['0.00001', 5]]) {
  const tick = new Tick(ts);
  let bad = 0; const examples = [];
  for (let i = 0; i < 10000; i++) {
    const units = Math.floor(rnd() * 1e9);                       // integer number of ticks
    const str = (units / 10 ** dec).toFixed(dec);                // exchange-style string
    const got = tick.parse(str);
    if (got.toFixed(dec) !== str) { bad++; if (examples.length < 3) examples.push([str, got]); }
  }
  out[`H2_tick_${ts}`] = { n: 10000, mismatches: bad, examples, pass: bad === 0 };
}

// ---------- H3: missed diff update ----------
let snapCb = null;
const feed = { subscribe: () => ({}), getOrderBookSnapshot: (sym, cb) => { snapCb = cb; } };
const book = new Book(feed, 'BTCUSDT', '0.01');
await new Promise(r => setTimeout(r, 2100));                     // its constructor waits 2 s before asking for the snapshot
snapCb({ lastUpdateId: 100, bids: [['100.00', '1.00']], asks: [['100.10', '1.00']] });
const diff = (U, u, price, qty) => ({ U, u, a: [[price, qty]], b: [] });
book.onDepth(diff(101, 105, '100.20', '2.00'));
book.onDepth(diff(110, 115, '100.30', '3.00'));                  // 106-109 never arrived
const applied = book.book[100.3] !== undefined;
out.H3_gap = { gap_update_applied: applied, errors: book.errors.length, log: book.log.length,
               isSnapshotParsed: book.isSnapshotParsed, pass: !applied || book.errors.length > 0 };

// ---------- H4 (EXPLORATORY, after reading the code; not pre-registered): sizes and aggregation ----------
book.onTrade({ t: 1, m: false, p: '100.10', q: '0.004', T: Date.now() });
const tr = book.trades[book.trades.length - 1];
book.onDepth(diff(116, 116, '100.40', '0.003'));
const tick2 = new Tick('0.01', 10);
out.H4_exploratory = {
  trade_size_input: '0.004', trade_size_stored: tr.size,
  depth_qty_input: '0.003', depth_qty_stored: book.book[100.4],
  aggregate_10_parseStep_100_27: tick2.parseStep('100.27'), expected_step_0_1: 100.3,
  getAggregate_returns: tick2.getAggregate(),
};

writeFileSync(outPath, JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 1).slice(0, 2000));
process.exit(0);
