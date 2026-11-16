"""S30 pysystemtrade checks P2-P8 (rules: PREREGISTERED.md).

Usage (venv with pysystemtrade installed editable; run with the repo as the
working directory, because pysystemtrade resolves its data and config paths
relative to its package):
    python s30_pysystemtrade_checks.py out.json
"""
import json
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
out = {}

# ---------------- P2 24/7 data folded into business days ----------------
from syscore.pandas.frequency import resample_prices_to_business_day_index

idx = pd.date_range("2024-03-04 00:00", periods=28 * 24, freq="h")  # Mon 4 Mar 2024, 4 weeks
s = pd.Series(np.arange(len(idx), dtype=float), index=idx)  # value = hours since start
d = resample_prices_to_business_day_index(s)
lab = {}
for day in d.index[:7]:
    v = d.loc[day]
    lab[str(day.date()) + " " + day.day_name()] = str(idx[int(v)])
moves_kept = float(d.diff().sum()) + float(d.iloc[0] - s.iloc[0])
out["P2_247_business_days"] = {
    "label_to_source_hour": lab,
    "labels_present": sorted({x.day_name() for x in d.index}),
    "total_move_hourly": float(s.iloc[-1] - s.iloc[0]),
    "total_move_daily": moves_kept,
    "pass_no_move_lost": bool(abs(moves_kept - (s.iloc[-1] - s.iloc[0])) < 1e-9),
}

# ---------------- P3a cost formula ----------------
from sysdata.csv.csv_instrument_data import csvFuturesInstrumentData
from sysdata.csv.csv_spread_costs import csvSpreadCostData
from sysobjects.instruments import instrumentCosts

meta = csvFuturesInstrumentData().get_instrument_data("BITCOIN").meta_data
spread = csvSpreadCostData().get_spread_cost("BITCOIN")
costs = instrumentCosts.from_meta_data_and_spread_cost(meta, spread)
c = costs.calculate_cost_instrument_currency(2, block_price_multiplier=meta.Pointsize, price=60000.0)
hand = 2 * spread * meta.Pointsize + max(2 * meta.PerBlock, meta.PerTrade, meta.Percentage * 2 * 60000 * meta.Pointsize)
out["P3a_cost_formula"] = {"pysystemtrade": float(c), "hand": float(hand), "spread_cost_cfg": float(spread),
                           "per_block_cfg": float(meta.PerBlock), "pointsize": float(meta.Pointsize),
                           "pass": bool(abs(c - hand) < 1e-9)}

# ---------------- BTC-only chapter-15 system ----------------
from sysdata.config.configdata import Config
from systems.provided.futures_chapter15.basesystem import futures_system

cfg = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
cfg.instruments = ["BITCOIN"]
cfg.instrument_weights = dict(BITCOIN=1.0)
cfg.instrument_div_multiplier = 1.0
t0 = time.perf_counter()
system = futures_system(config=cfg)
system.set_logging_level("off") if hasattr(system, "set_logging_level") else None
acc = system.accounts.pandl_for_instrument("BITCOIN")
total = float(acc.sum()) if hasattr(acc, "sum") else None
elapsed = time.perf_counter() - t0
out["P7_speed"] = {"seconds_btc_only_backtest": round(elapsed, 2)}

# ---------------- P3b costs in the account curve ----------------
try:
    pos = system.accounts.get_buffered_position("BITCOIN", roundpositions=True)
except TypeError:
    pos = system.accounts.get_buffered_position("BITCOIN")
price = system.rawdata.get_daily_prices("BITCOIN") if hasattr(system.rawdata, "get_daily_prices") else system.data.daily_prices("BITCOIN")
gross = acc.gross if hasattr(acc, "gross") else None
cost_series = acc.costs if hasattr(acc, "costs") else None
pos_d = pos.reindex(price.index, method="ffill").fillna(0)
trades = pos_d.diff().fillna(pos_d.iloc[0])
# the account curve trades at the price of the day the position changes
hand_costs = sum(costs.calculate_cost_instrument_currency(abs(q), block_price_multiplier=meta.Pointsize, price=float(p))
                 for q, p in zip(trades.values, price.values) if q != 0 and not np.isnan(p))
sys_costs = float(-cost_series.sum()) if cost_series is not None else None
out["P3b_costs_in_backtest"] = {
    "n_position_changes": int((trades != 0).sum()),
    "contracts_traded": float(trades.abs().sum()),
    "system_total_costs": sys_costs,
    "hand_total_costs_daily_close": float(hand_costs),
    "rel_diff": (abs(sys_costs - hand_costs) / hand_costs) if sys_costs and hand_costs else None,
    "pass": bool(sys_costs is not None and abs(sys_costs - hand_costs) <= 1e-6 * hand_costs),
    "use_SR_costs": bool(system.config.get_element_or_default("use_SR_costs", False)),
}

# ---------------- P4 sizing ----------------
ps = system.positionSize
ss = ps.get_subsystem_position("BITCOIN")
fc = ps.get_combined_forecast("BITCOIN")
cash_vol = ps.get_daily_cash_vol_target()
ivv = ps.get_instrument_value_vol("BITCOIN")
last = ss.index[-1]
vol_scalar_last = cash_vol / ivv.reindex(fc.index, method="ffill").loc[last]
hand_pos = float(fc.loc[last]) / system.config.average_absolute_forecast * vol_scalar_last
capital = system.config.notional_trading_capital
vt = system.config.percentage_vol_target
out["P4_sizing"] = {
    "date": str(last), "system_position": float(ss.loc[last]), "hand_position": hand_pos,
    "forecast": float(fc.loc[last]), "daily_cash_vol_target": float(cash_vol),
    "capital_x_volpct_over_16": capital * vt / 100 / 16,
    "pass": bool(abs(ss.loc[last] - hand_pos) <= 1e-9 * max(1, abs(hand_pos))),
}
# value-vol check: block value = price * pointsize * 0.01; ccy vol = block * daily % vol
bv = ps.get_block_value("BITCOIN")
up = ps.get_underlying_price("BITCOIN")
out["P4_sizing"]["block_value_matches_price_x_point_x_0.01"] = bool(np.allclose(
    bv.dropna().values, (up.ffill() * meta.Pointsize * 0.01).reindex(bv.dropna().index).values, rtol=1e-12))

# ---------------- P5 production controls ----------------
from sysobjects.production.override import Override, override_reduce_only, override_close, override_no_trading
from sysexecution.orders.instrument_orders import instrumentOrder


def trade_after(override, position, trade):
    o = instrumentOrder("strat", "BITCOIN", trade)
    return int(override.apply_override(position, o).trade[0])


p5 = {"overrides": {
    "reduce_only_growing(+2 at 3)": trade_after(Override(override_reduce_only), 3, 2),
    "reduce_only_shrinking(-2 at 3)": trade_after(Override(override_reduce_only), 3, -2),
    "reduce_only_flipping(-5 at 3)": trade_after(Override(override_reduce_only), 3, -5),
    "close(+2 at 3)": trade_after(Override(override_close), 3, 2),
    "no_trading(+2 at 3)": trade_after(Override(override_no_trading), 3, 2),
    "float_0.5(+2 at 3)": trade_after(Override(0.5), 3, 2),
}}
p5["overrides_pass"] = (p5["overrides"]["reduce_only_growing(+2 at 3)"] == 0
                        and p5["overrides"]["reduce_only_shrinking(-2 at 3)"] == -2
                        and p5["overrides"]["close(+2 at 3)"] == -3
                        and p5["overrides"]["no_trading(+2 at 3)"] == 0)
from sysobjects.production.trade_limits import tradeLimit, listOfTradeLimits
from sysobjects.production.tradeable_object import instrumentStrategy

ist = instrumentStrategy(strategy_name="strat", instrument_code="BITCOIN")
tl = tradeLimit(3, ist, period_days=1, trades_since_last_reset=2)
p5["trade_limit_3_used_2_proposed_5"] = int(listOfTradeLimits([tl]).what_trade_is_possible(5))
from sysobjects.production.position_limits import positionLimitForInstrument, positionLimitAndPosition

pl = positionLimitAndPosition(positionLimitForInstrument("BITCOIN", 4), 3)
o = instrumentOrder("strat", "BITCOIN", 3)
p5["position_limit_4_at_3_proposed_+3"] = int(pl.apply_position_limit_to_order(o).trade[0])
out["P5_controls"] = p5

# ---------------- P6 back-adjustment ----------------
from sysdata.csv.csv_adjusted_prices import csvFuturesAdjustedPricesData
from sysdata.csv.csv_multiple_prices import csvFuturesMultiplePricesData

adj = csvFuturesAdjustedPricesData().get_adjusted_prices("BITCOIN")
mult = csvFuturesMultiplePricesData().get_multiple_prices("BITCOIN")
df = pd.concat([adj.rename("adj"), mult["PRICE"], mult["PRICE_CONTRACT"]], axis=1).dropna()
same = df["PRICE_CONTRACT"] == df["PRICE_CONTRACT"].shift(1)
dadj = df["adj"].diff()
dpx = df["PRICE"].diff()
ok = (dadj - dpx).abs() <= 1e-6 * df["PRICE"].abs()
rows = same & dadj.notna()
rolls = df.index[(~same) & df["PRICE_CONTRACT"].shift(1).notna()]
gaps = (df["adj"] - df["PRICE"]).diff().loc[rolls].abs()
out["P6_back_adjustment"] = {
    "rows_checked": int(rows.sum()), "rows_matching": int((ok & rows).sum()),
    "share_matching": float((ok & rows).sum() / rows.sum()),
    "n_rolls": int(len(rolls)), "largest_roll_gap_price_points": float(gaps.max()) if len(gaps) else 0.0,
    "pass": bool((ok & rows).sum() / rows.sum() >= 0.999),
    "first": str(df.index[0]), "last": str(df.index[-1]),
}

with open(sys.argv[1], "w") as fh:
    json.dump(out, fh, indent=2, default=str)
for k, v in out.items():
    print(k, json.dumps(v, default=str)[:700])

# ---------------- P3b follow-up (added AFTER the first run showed the gap; exploratory, not pre-registered) ----------------
from syscore.dateutils import generate_equal_dates_within_year

rpy = system.accounts.get_rolls_per_year("BITCOIN") if hasattr(system.accounts, "get_rolls_per_year") else None
posf = pos.astype(float)
roll_qty = 0.0
last_pos_date = posf.index[-1]
for year in sorted(set(posf.index.year)):
    dates = generate_equal_dates_within_year(year, rpy)
    prev = generate_equal_dates_within_year(year - 1, rpy)[-1]
    alld = [prev] + dates
    for i, dte in enumerate(dates):
        avg = posf[alld[i]:alld[i + 1]].abs().mean()
        if np.isnan(avg) or dte > last_pos_date or avg == 0:
            continue
        roll_qty += 2 * avg
roll_cost = roll_qty * (spread * meta.Pointsize + meta.PerBlock)
out["P3b_followup_roll_costs"] = {
    "rolls_per_year": rpy, "pseudo_roll_contracts": roll_qty, "pseudo_roll_cost": roll_cost,
    "trading_plus_roll_cost": hand_costs + roll_cost, "system_total_costs": sys_costs,
    "rel_diff": abs(hand_costs + roll_cost - sys_costs) / sys_costs,
}
with open(sys.argv[1], "w") as fh:
    json.dump(out, fh, indent=2, default=str)
print("P3b_followup", json.dumps(out["P3b_followup_roll_costs"]))

# ---------------- P3b follow-up 2 (exploratory): switch off cost normalisation and roll pseudo-fills ----------------
cfg2 = Config("systems.provided.futures_chapter15.futuresconfig.yaml")
cfg2.instruments = ["BITCOIN"]
cfg2.instrument_weights = dict(BITCOIN=1.0)
cfg2.instrument_div_multiplier = 1.0
cfg2.vol_normalise_currency_costs = False
cfg2.multiply_roll_costs_by = 0.0
s2 = futures_system(config=cfg2)
acc2 = s2.accounts.pandl_for_instrument("BITCOIN")
pc2 = acc2.pandl_calculator_with_costs
trade_fills = [f for f in pc2.list_of_all_fills() if f not in pc2.pseudo_fills_from_holding] if hasattr(pc2, "list_of_all_fills") else []
no_slip_flag = sum(1 for f in trade_fills if not f.price_requires_slippage_adjustment)
sys2 = float(-acc2.costs.sum())
comm_only = float(trades.abs().sum() * meta.PerBlock)
out["P3b_followup2_raw_costs"] = {
    "system_total_costs_raw": sys2,
    "hand_commission_plus_spread": float(hand_costs),
    "hand_commission_only": comm_only,
    "trade_fills": len(trade_fills), "trade_fills_without_slippage_flag": no_slip_flag,
    "matches_commission_plus_spread": bool(abs(sys2 - hand_costs) <= 1e-6 * hand_costs),
    "matches_commission_only": bool(abs(sys2 - comm_only) <= 1e-6 * comm_only),
}
with open(sys.argv[1], "w") as fh:
    json.dump(out, fh, indent=2, default=str)
print("P3b_followup2", json.dumps(out["P3b_followup2_raw_costs"]))
