"""S34 FinRL checks F2-F5 (rules: PREREGISTERED.md).

Usage (venv with FinRL installed, run from an empty working folder because FinRL writes results/ there):
    python -I s34_finrl_checks.py out.json
"""
import contextlib
import io
import json
import sys
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
out_path = sys.argv[1]
out = {}

from finrl.meta.env_cryptocurrency_trading.env_multiple_crypto import CryptoEnv  # noqa: E402
from finrl.meta.env_stock_trading.env_stocktrading import StockTradingEnv  # noqa: E402
from finrl.meta.preprocessor.preprocessors import FeatureEngineer  # noqa: E402
from finrl import config  # noqa: E402


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def make_env(df, tech, cost=0.0, cash=1_000_000):
    n = df.tic.nunique()
    return StockTradingEnv(df=df, stock_dim=n, hmax=100, initial_amount=cash, num_stock_shares=[0] * n,
                           buy_cost_pct=[cost] * n, sell_cost_pct=[cost] * n, reward_scaling=1e-4,
                           state_space=1 + 2 * n + len(tech) * n, action_space=n, tech_indicator_list=tech,
                           print_verbosity=10**9)


# ---------- F2 fill timing ----------
dates = pd.date_range("2024-01-01", periods=6, freq="D").strftime("%Y-%m-%d")
closes = [100.0, 110.0, 121.0, 133.1, 146.41, 161.051]
df1 = pd.DataFrame({"date": dates, "tic": "AAA", "open": closes, "high": closes, "low": closes, "close": closes,
                    "volume": 1e6})
df1.index = df1.date.factorize()[0]
env = make_env(df1, [], cost=0.0)
obs, _ = env.reset()
seen_price = float(obs[1])
cash0 = float(env.state[0])
env.step(np.array([0.1]))  # 0.1 * hmax 100 = 10 shares
shares = float(env.state[2])
paid_per_share = (cash0 - float(env.state[0])) / shares
out["F2_fill_timing"] = {"price_in_observation": seen_price, "paid_per_share": paid_per_share,
                         "next_bar_close": closes[1], "shares": shares,
                         "same_bar": bool(abs(paid_per_share - seen_price) < 1e-9),
                         "pass": bool(abs(paid_per_share - closes[1]) < 1e-9)}

# ---------- F3 costs ----------
env = make_env(df1, [], cost=0.001)
env.reset()
c0 = float(env.state[0])
env.step(np.array([0.1]))     # buy 10 @ 100
env.step(np.array([-0.1]))    # sell 10 @ 110
hand_cash = c0 - 10 * 100 * 1.001 + 10 * 110 * 0.999
hand_cost = 10 * 100 * 0.001 + 10 * 110 * 0.001
out["F3_costs"] = {"cash": float(env.state[0]), "hand_cash": hand_cash, "cost": float(env.cost),
                   "hand_cost": hand_cost, "shares": float(env.state[2]),
                   "pass": bool(abs(env.state[0] - hand_cash) < 1e-9 and abs(env.cost - hand_cost) < 1e-9
                                and env.state[2] == 0)}

# ---------- F4 slice test ----------
rng = np.random.default_rng(20261116)
days = pd.bdate_range("2020-01-01", periods=800).strftime("%Y-%m-%d")
rows = []
for tic, p0 in (("AAA", 100.0), ("BBB", 50.0), ("CCC", 80.0)):
    c = p0 * np.exp(np.cumsum(rng.normal(0, 0.02, len(days))))
    h = c * (1 + rng.uniform(0, 0.02, len(days)))
    lo = c * (1 - rng.uniform(0, 0.02, len(days)))
    o = c * (1 + rng.normal(0, 0.005, len(days)))
    rows.append(pd.DataFrame({"date": days, "tic": tic, "open": o, "high": h, "low": lo, "close": c,
                              "volume": rng.uniform(1e5, 1e6, len(days))}))
raw = pd.concat(rows).sort_values(["date", "tic"]).reset_index(drop=True)
fe = FeatureEngineer(use_technical_indicator=True, tech_indicator_list=config.INDICATORS, use_vix=False,
                     use_turbulence=True, user_defined_feature=True)
full = quiet(fe.preprocess_data, raw.copy())
cut_day = days[599]
cut = quiet(fe.preprocess_data, raw[raw.date <= cut_day].copy())
cols = config.INDICATORS + ["turbulence", "daily_return"]
a = full[full.date <= cut_day].set_index(["date", "tic"])[cols].sort_index()
b = cut.set_index(["date", "tic"])[cols].sort_index()
diff = (a - b).abs().max()
out["F4_slice"] = {"cut_day_index": 599, "max_abs_diff": {k: float(v) for k, v in diff.items()},
                   "pass": bool((diff <= 1e-9).all())}

# ---------- F4b survivorship ----------
raw_b = raw[~((raw.tic == "CCC") & (raw.date > days[-11]))].copy()
cleaned = quiet(FeatureEngineer(use_technical_indicator=False).clean_data, raw_b)
present = sorted(cleaned.tic.unique())
ccc_rows_before = int(((raw_b.tic == "CCC")).sum())
ccc_rows_after = int(((cleaned.tic == "CCC")).sum())
out["F4b_survivorship"] = {"tickers_after_clean": present, "CCC_rows_in_input": ccc_rows_before,
                           "CCC_rows_after_clean": ccc_rows_after, "pass": bool(ccc_rows_after == ccc_rows_before)}

# ---------- F5 crypto env ----------
price = np.array([[30000.0, 2000.0], [30100.0, 2010.0], [29900.0, 1990.0], [30200.0, 2020.0]])
tech = price.copy()
cenv = CryptoEnv({"price_array": price, "tech_array": tech}, lookback=1, initial_capital=1e6,
                 buy_cost_pct=1e-3, sell_cost_pct=1e-3)
cenv.reset()
norm = cenv.action_norm_vector.copy()
s, r, d, _ = cenv.step(np.array([1.0 / norm[0] * 2, 0.0]))  # ask for 2 BTC
bought, cash_after = float(cenv.stocks[0]), float(cenv.cash)
hand_cash = 1e6 - 30100.0 * bought * 1.001
s, r, d, _ = cenv.step(np.array([-1.0 / norm[0] * 5, -1.0 / norm[1] * 5]))  # sell 5 BTC (holds 2), sell 5 ETH (holds 0)
short_attempt = {"btc_after": float(cenv.stocks[0]), "eth_after": float(cenv.stocks[1])}
# action normaliser depends on how the first price prints
n_a = CryptoEnv({"price_array": np.array([[16547.5], [16600.0]]), "tech_array": np.zeros((2, 1))}).action_norm_vector
n_b = CryptoEnv({"price_array": np.array([[16547.500001], [16600.0]]), "tech_array": np.zeros((2, 1))}).action_norm_vector
out["F5_crypto_env"] = {"fill_price_bar": "price at time+1 (next bar after the observation)",
                        "bought_btc": bought, "cash_after": cash_after, "hand_cash": hand_cash,
                        "fees_exact": bool(abs(cash_after - hand_cash) < 1e-6),
                        "whole_units_only": bool(bought == int(bought)),
                        "short_attempt": short_attempt,
                        "can_short": bool(short_attempt["btc_after"] < 0 or short_attempt["eth_after"] < 0),
                        "funding_modelled": "no funding term in the code (read)",
                        "action_scale_16547.5": float(n_a[0]), "action_scale_16547.500001": float(n_b[0])}

with open(out_path, "w") as fh:
    json.dump(out, fh, indent=2, default=str)
for k, v in out.items():
    print(k, json.dumps(v, default=str)[:700])
