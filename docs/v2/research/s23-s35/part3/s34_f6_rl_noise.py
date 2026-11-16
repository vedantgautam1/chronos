"""S34 FinRL F6: PPO on pure noise (rules: PREREGISTERED.md). Seeds 0-4, all reported.

Prices are martingales: log-returns N(-sigma^2/2, sigma^2), sigma = 3% a day, so the expected price change is zero.
Run from an empty folder (FinRL writes results/ and tensorboard files there).
Usage: python -I s34_f6_rl_noise.py out.json
"""
import contextlib
import io
import json
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
from finrl import config  # noqa: E402
from finrl.agents.stablebaselines3.models import DRLAgent  # noqa: E402
from finrl.meta.env_stock_trading.env_stocktrading import StockTradingEnv  # noqa: E402
from finrl.meta.preprocessor.preprocessors import FeatureEngineer, data_split  # noqa: E402

SIGMA, N_DAYS, SPLIT, STEPS, COST = 0.03, 1500, 1000, 20_000, 0.001
TECH = config.INDICATORS


def sharpe(values):
    r = pd.Series(values).pct_change().dropna()
    return float(r.mean() / r.std(ddof=1) * np.sqrt(365)) if r.std(ddof=1) > 0 else 0.0


def env_for(df):
    n = df.tic.nunique()
    return StockTradingEnv(df=df, stock_dim=n, hmax=100, initial_amount=1_000_000, num_stock_shares=[0] * n,
                           buy_cost_pct=[COST] * n, sell_cost_pct=[COST] * n, reward_scaling=1e-4,
                           state_space=1 + 2 * n + len(TECH) * n, action_space=n, tech_indicator_list=TECH,
                           print_verbosity=10**9)


def buy_hold(df):
    piv = df.pivot(index="date", columns="tic", values="close")
    w = (piv / piv.iloc[0]).mean(axis=1)
    return sharpe(w.values)


results = []
for seed in (0, 1, 2, 3, 4):
    t0 = time.perf_counter()
    rng = np.random.default_rng(1000 + seed)
    days = pd.bdate_range("2015-01-01", periods=N_DAYS).strftime("%Y-%m-%d")
    frames = []
    for tic in ("AAA", "BBB", "CCC"):
        lr = rng.normal(-SIGMA**2 / 2, SIGMA, N_DAYS)
        c = 100 * np.exp(np.cumsum(lr))
        frames.append(pd.DataFrame({"date": days, "tic": tic, "open": c, "high": c * 1.01, "low": c * 0.99,
                                    "close": c, "volume": 1e6}))
    raw = pd.concat(frames).sort_values(["date", "tic"]).reset_index(drop=True)
    with contextlib.redirect_stdout(io.StringIO()):
        feat = FeatureEngineer(use_technical_indicator=True, tech_indicator_list=TECH, use_turbulence=False,
                               user_defined_feature=False).preprocess_data(raw)
    train = data_split(feat, days[0], days[SPLIT])          # [start, end) per FinRL's data_split
    test = data_split(feat, days[SPLIT], days[-1] + "x")    # to the end
    with contextlib.redirect_stdout(io.StringIO()):
        env_train, _ = env_for(train).get_sb_env()
        agent = DRLAgent(env=env_train)
        model = agent.get_model("ppo", seed=seed, verbose=0)
        model = DRLAgent.train_model(model, tb_log_name=f"ppo_{seed}", total_timesteps=STEPS)
        acc_in, _ = DRLAgent.DRL_prediction(model, env_for(train), deterministic=True)
        acc_out, _ = DRLAgent.DRL_prediction(model, env_for(test), deterministic=True)
    row = {"seed": seed, "train_days": int(train.date.nunique()), "test_days": int(test.date.nunique()),
           "sharpe_in": sharpe(acc_in.account_value.values), "sharpe_out": sharpe(acc_out.account_value.values),
           "buyhold_in": buy_hold(train), "buyhold_out": buy_hold(test),
           "final_value_in": float(acc_in.account_value.iloc[-1]), "final_value_out": float(acc_out.account_value.iloc[-1]),
           "seconds": round(time.perf_counter() - t0, 1)}
    results.append(row)
    print(json.dumps(row), flush=True)

si = np.array([r["sharpe_in"] for r in results])
so = np.array([r["sharpe_out"] for r in results])
summary = {"mean_sharpe_in": float(si.mean()), "mean_sharpe_out": float(so.mean()),
           "se_out": float(so.std(ddof=1) / np.sqrt(len(so))),
           "hyp_in_gt_out": bool(si.mean() > so.mean()),
           "hyp_out_within_2se_of_0": bool(abs(so.mean()) <= 2 * so.std(ddof=1) / np.sqrt(len(so)))}
with open(sys.argv[1], "w") as fh:
    json.dump({"settings": {"sigma": SIGMA, "days": N_DAYS, "split": SPLIT, "timesteps": STEPS, "cost": COST,
                            "annualisation": "sqrt(365)", "ppo_params": config.PPO_PARAMS},
               "seeds": results, "summary": summary}, fh, indent=2)
print(json.dumps(summary))
