# B4 toy strategy (copied at run time to freqtrade/tests/strategy/strats/s19deep/).
# Scenarios: clean, lead1 (one bar ahead), fullmean (whole-series statistic),
# ema_warmup (recursive indicator; for recursive-analysis only), sma_clean (non-recursive).
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy
from freqtrade.strategy.parameters import CategoricalParameter


class s19deep_leaks(IStrategy):
    INTERFACE_VERSION = 3
    minimal_roi = {"0": 0.02}
    stoploss = -0.05
    timeframe = "5m"
    startup_candle_count: int = 30
    scenario = CategoricalParameter(
        ["clean", "lead1", "fullmean", "fullmean2", "ema_warmup", "sma_clean"], default="clean", space="buy"
    )

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        s = self.scenario.value
        dataframe["sma20"] = dataframe["close"].rolling(20).mean()
        if s == "lead1":
            dataframe["next_close"] = dataframe["close"].shift(-1)
        if s in ("fullmean", "fullmean2"):
            dataframe["fullmean"] = dataframe["close"].mean()
        if s == "ema_warmup":
            dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        s = self.scenario.value
        if s == "lead1":
            dataframe.loc[dataframe["next_close"] > dataframe["close"] * 1.001, "enter_long"] = 1
        elif s == "fullmean":
            dataframe.loc[dataframe["close"] < dataframe["fullmean"] * 0.99, "enter_long"] = 1
        elif s == "fullmean2":
            # revised after the first run produced 0 signals (inconclusive): same leak, trades more often
            dataframe.loc[(dataframe["close"] > dataframe["fullmean"]) & (dataframe["close"] > dataframe["sma20"]), "enter_long"] = 1
        else:
            dataframe.loc[dataframe["close"] > dataframe["sma20"] * 1.002, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["close"] < dataframe["sma20"], "exit_long"] = 1
        return dataframe
