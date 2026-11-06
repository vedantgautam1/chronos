# B3 toy strategy: MA crossover with hyperoptable lengths (copied to freqtrade/tests/strategy/strats/s19deep/).
from pandas import DataFrame

from freqtrade.strategy import IntParameter, IStrategy


class s19deep_hyper(IStrategy):
    INTERFACE_VERSION = 3
    minimal_roi = {"0": 100}
    stoploss = -0.10
    timeframe = "1h"
    startup_candle_count: int = 200
    fast = IntParameter(5, 50, default=10, space="buy")
    slow = IntParameter(20, 200, default=50, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for n in set(list(self.fast.range) + list(self.slow.range)):
            dataframe[f"ma{n}"] = dataframe["close"].rolling(n).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        f, s = dataframe[f"ma{self.fast.value}"], dataframe[f"ma{self.slow.value}"]
        dataframe.loc[(f > s) & (f.shift(1) <= s.shift(1)), "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        f, s = dataframe[f"ma{self.fast.value}"], dataframe[f"ma{self.slow.value}"]
        dataframe.loc[(f < s) & (f.shift(1) >= s.shift(1)), "exit_long"] = 1
        return dataframe
