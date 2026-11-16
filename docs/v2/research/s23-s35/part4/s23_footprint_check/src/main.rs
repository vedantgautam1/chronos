//! S23 flowsurface W3 known-answer check (rules: ../PREREGISTERED.md). Prints JSON.
use data::chart::kline::footprint::KlineTrades;
use exchange::unit::price::{Price, PriceStep};
use exchange::unit::qty::Qty;
use exchange::{Timeframe, Trade, UnixMs};

fn main() {
    let step = PriceStep { units: Price::from_f64(0.5).units };
    // (price, qty, is_sell, expected bin): ties are half-way cases; its code says "round half away from zero"
    let cases: [(f64, f64, bool, f64); 7] = [
        (100.20, 1.0, false, 100.0),
        (100.25, 2.0, true, 100.5),  // tie
        (100.75, 3.0, false, 101.0), // tie
        (99.75, 4.0, true, 100.0),   // tie
        (100.30, 5.0, false, 100.5),
        (100.30, 6.0, false, 100.5), // same price twice
        (99.70, 7.0, true, 99.5),
    ];
    let mut fp = KlineTrades::new();
    for (i, (p, q, s, _)) in cases.iter().enumerate() {
        let t = Trade { time: UnixMs::from_millis(1_700_000_000_000 + i as u64), is_sell: *s,
                        price: Price::from_f64(*p), qty: Qty::from_f64(*q) };
        fp.add_trade_to_nearest_bin(&t, step);
    }
    let mut ok_bins = true;
    let mut rows = Vec::new();
    for bin in [99.5, 100.0, 100.5, 101.0] {
        let (mut hb, mut hs) = (0.0, 0.0);
        for (_, q, s, e) in cases.iter() {
            if (*e - bin).abs() < 1e-12 { if *s { hs += q } else { hb += q } }
        }
        let g = fp.trades.get(&Price::from_f64(bin));
        let (gb, gs) = g.map(|g| (g.buy_qty.to_f64(), g.sell_qty.to_f64())).unwrap_or((0.0, 0.0));
        if (gb - hb).abs() > 1e-12 || (gs - hs).abs() > 1e-12 { ok_bins = false; }
        rows.push(format!("{{\"bin\":{bin},\"buy\":{gb},\"sell\":{gs},\"hand_buy\":{hb},\"hand_sell\":{hs}}}"));
    }
    // time buckets: a trade exactly at 00:05:00 belongs to the 00:05 bar ([start, end))
    let start = 1_700_000_100_000u64 / 300_000 * 300_000;
    let at_boundary = UnixMs::from_millis(start + 300_000).floor_to(Timeframe::M5);
    let just_before = UnixMs::from_millis(start + 299_999).floor_to(Timeframe::M5);
    let ok_time = u64::from(at_boundary) == start + 300_000 && u64::from(just_before) == start;
    println!("{{\"W3_footprint\":{{\"bins\":[{}],\"bins_exact\":{ok_bins},\"time_half_open\":{ok_time},\"pass\":{}}}}}",
             rows.join(","), ok_bins && ok_time);
}
