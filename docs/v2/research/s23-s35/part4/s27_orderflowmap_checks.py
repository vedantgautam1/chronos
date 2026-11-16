"""S27 OrderFlowMap checks O1-O3 (rules: PREREGISTERED.md). Headless Chromium via Playwright.

Usage: python -I s27_orderflowmap_checks.py /path/to/OrderFlowMap /path/to/lightweight-charts.standalone.production.js out.json
(the second file is lightweight-charts 5.0.9 from npm, served in place of the CDN copy for O2/O3)
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

repo, lwc_path, out_path = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
url = (repo / "index.html").resolve().as_uri()
out = {}

TAPE_JS = r"""
(args) => {
  // deterministic synthetic tape with TRUE aggressor sides
  let s = 20261116;
  const rnd = () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const tick = 0.05, N = 5000;
  let mid = 24500.0, cumVol = 0, t0 = 1763251200000;
  const tape = [];
  for (let i = 0; i < N; i++) {
    const u = rnd(); if (u < 0.15) mid += tick; else if (u < 0.30) mid -= tick;
    const bid = Math.round((mid - tick / 2) / tick) * tick, ask = bid + tick;
    const buy = rnd() < 0.5, qty = 1 + Math.floor(rnd() * 50);
    cumVol += qty;
    tape.push({ i, side: buy ? 'B' : 'S', qty, price: buy ? ask : bid, bid, ask, cumVol, ts: t0 + i * 100 });
  }
  const results = {};
  for (const k of args.cadences) {
    RUNNING = false; trades.length = 0; cvd = 0;
    prevTick.volume = null; prevTick.ltp = null; prevTick.lastSide = 'B';
    let correct = 0, total = 0, inferredCvd = 0, trueCvd = 0, lumps = 0, firstLumpDefaultB = null;
    let lastIdx = -1;
    for (let j = k - 1; j < N; j += k) {
      const tr = tape[j];
      const before = trades.length;
      processLiveData({ ltp: tr.price, volume: tr.cumVol, ltt: tr.ts,
        depth: { buy: [{ price: tr.bid, quantity: 100 }], sell: [{ price: tr.ask, quantity: 100 }] } });
      if (lastIdx >= 0 && trades.length > before) {
        const inf = trades[trades.length - 1];
        lumps++;
        let lumpVol = 0;
        for (let m = lastIdx + 1; m <= j; m++) {
          const q = tape[m].qty; lumpVol += q; total += q;
          trueCvd += tape[m].side === 'B' ? q : -q;
          if (tape[m].side === inf.side) correct += q;
        }
        inferredCvd += inf.side === 'B' ? inf.qty : -inf.qty;
        if (Math.abs(inf.qty - lumpVol) > 1e-9) results['qty_mismatch_' + k] = true;
      }
      lastIdx = j;
    }
    results[k] = { snapshots_every_k_trades: k, inferred_trades: lumps, correctly_signed_volume_share: correct / total,
                   true_cvd: trueCvd, inferred_cvd: inferredCvd, cvd_error: inferredCvd - trueCvd, volume_counted: total };
  }
  return results;
}
"""

SIM_JS = r"""
() => {
  RUNNING = false; trades.length = 0; cvd = 0;
  let base = 2000000000;
  for (let i = 0; i < 300; i++) simulateTick(base + i);
  const sum = trades.reduce((a, t) => a + (t.side === 'B' ? t.qty : -t.qty), 0);
  return { ticks: 300, trades: trades.length, cvd: cvd, sum_signed_trades: sum, pass: cvd === sum };
}
"""

with sync_playwright() as p:
    b = p.chromium.launch()
    # ---------- O1: everything off the network ----------
    page = b.new_page()
    errs, blocked = [], []
    page.on("pageerror", lambda e: errs.append(str(e)[:200]))
    page.route("**/*", lambda r: (blocked.append(r.request.url), r.abort()) if not r.request.url.startswith("file:")
               else r.continue_())
    page.goto(url)
    page.wait_for_timeout(2000)
    has_lwc = page.evaluate("typeof LightweightCharts !== 'undefined'")
    canvases = page.evaluate("document.querySelectorAll('canvas').length")
    out["O1_offline"] = {"blocked_requests": blocked, "page_errors": errs[:5], "LightweightCharts_defined": has_lwc,
                         "canvas_count": canvases, "pass": bool(has_lwc and not errs)}
    page.close()
    # ---------- O2/O3 with the CDN file served locally ----------
    page = b.new_page()
    errs2 = []
    page.on("pageerror", lambda e: errs2.append(str(e)[:200]))
    page.route("https://cdn.jsdelivr.net/**", lambda r: r.fulfill(path=lwc_path, content_type="application/javascript"))
    page.route("ws://**", lambda r: r.abort())
    page.goto(url)
    page.wait_for_timeout(1500)
    out["O2_live_inference"] = page.evaluate(TAPE_JS, {"cadences": [1, 5]})
    r1 = out["O2_live_inference"]["1"]["correctly_signed_volume_share"]
    out["O2_live_inference"]["pass"] = bool(r1 >= 0.95)
    out["O3_sim_cvd"] = page.evaluate(SIM_JS)
    out["page_errors_O2_O3"] = errs2[:5]
    b.close()

with open(out_path, "w") as fh:
    json.dump(out, fh, indent=2, default=str)
print(json.dumps(out, default=str)[:3000])
