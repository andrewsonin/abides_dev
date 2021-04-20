from bisect import bisect_left
from math import sqrt

import pandas as pd

from oracle import Oracle
from util import log_print


class ExternalFileOracle(Oracle):
    """
    Oracle using an external price series as the fundamental. The external series are specified files in the ABIDES
    config. If an agent requests the fundamental value in between two timestamps the returned fundamental value is
    linearly interpolated.
    """
    __slots__ = (
        "mkt_open",
        "symbols",
        "fundamentals",
        "f_log"
    )

    def __init__(self, symbols):
        self.mkt_open = None
        self.symbols = symbols
        self.fundamentals = self.load_fundamentals()
        self.f_log = {symbol: [] for symbol in symbols}

    def load_fundamentals(self):
        """ Method extracts fundamentals for each symbol into DataFrames. Note that input files must be of the form
            generated by util/formatting/mid_price_from_orderbook.py.
        """
        fundamentals = {}
        log_print("Oracle: loading fundamental price series...")
        for symbol, params_dict in self.symbols.items():
            fundamental_file_path = params_dict['fundamental_file_path']
            log_print("Oracle: loading {}", fundamental_file_path)
            fundamental_df = pd.read_pickle(fundamental_file_path)
            fundamentals.update({symbol: fundamental_df})

        log_print("Oracle: loading fundamental price series complete!")
        return fundamentals

    def getDailyOpenPrice(self, symbol, mkt_open):

        # Remember market open time.
        self.mkt_open = mkt_open

        log_print("Oracle: client requested {} at market open: {}", symbol, mkt_open)

        # Find the opening historical price or this symbol.
        open_price = self.getPriceAtTime(symbol, mkt_open)
        log_print("Oracle: market open price was was {}", open_price)

        return int(round(open_price))

    def getPriceAtTime(self, symbol, query_time):
        """ Get the true price of a symbol at the requested time.
            :param symbol: which symbol to query
            :type symbol: str
            :param time: at this time
            :type time: pd.Timestamp
        """

        log_print("Oracle: client requested {} as of {}", symbol, query_time)

        fundamental_series = self.fundamentals[symbol]
        time_of_query = pd.Timestamp(query_time)

        series_open_time = fundamental_series.index[0]
        series_close_time = fundamental_series.index[-1]

        if time_of_query < series_open_time:  # time queried before open
            return fundamental_series[0]
        elif time_of_query > series_close_time:  # time queried after close
            return fundamental_series[-1]
        else:  # time queried during trading

            # find indices either side of requested time
            lower_idx = bisect_left(fundamental_series.index, time_of_query) - 1
            upper_idx = lower_idx + 1 if lower_idx < len(fundamental_series.index) - 1 else lower_idx

            # interpolate between values
            lower_val = fundamental_series[lower_idx]
            upper_val = fundamental_series[upper_idx]

            log_print(
                f"DEBUG: lower_idx: {lower_idx}, lower_val: {lower_val}, upper_idx: {upper_idx}, upper_val: {upper_val}")

            interpolated_price = self.getInterpolatedPrice(query_time, fundamental_series.index[lower_idx],
                                                           fundamental_series.index[upper_idx], lower_val, upper_val)
            log_print("Oracle: latest historical trade was {} at {}. Next historical trade is {}. "
                      "Interpolated price is {}", lower_val, query_time, upper_val, interpolated_price)

            self.f_log[symbol].append({'FundamentalTime': query_time, 'FundamentalValue': interpolated_price})

            return interpolated_price

    def observePrice(self, symbol, current_time, sigma_n=0.0001, random_state=None):
        """ Make observation of price at a given time.
        :param symbol: symbol for which to observe price
        :type symbol: str
        :param current_time: time of observation
        :type current_time: pd.Timestamp
        :param sigma_n: Observation noise parameter
        :type sigma_n: float
        :param random_state: random state for Agent making observation
        :type random_state: np.RandomState
        :return: int, price in cents
        """
        true_price = self.getPriceAtTime(symbol, current_time)
        if sigma_n == 0:
            observed = true_price
        else:
            observed = random_state.normal(loc=true_price, scale=sqrt(sigma_n))

        return int(round(observed))

    def getInterpolatedPrice(self, current_time, time_low, time_high, price_low, price_high):
        """ Get the price at current_time, linearly interpolated between price_low and price_high measured at times
            time_low and time_high
            :param current_time: time for which price is to be interpolated
            :type current_time: pd.Timestamp
            :param time_low: time of first fundamental value
            :type time_low: pd.Timestamp
            :param time_high: time of first fundamental value
            :type time_high: pd.Timestamp
            :param price_low: first fundamental value
            :type price_low: float
            :param price_high: first fundamental value
            :type price_high: float
            :return float of interpolated price:
        """
        log_print(
            f'DEBUG: current_time: {current_time} time_low {time_low} time_high: {time_high} price_low:  {price_low} price_high: {price_high}')
        delta_y = price_high - price_low
        delta_x = (time_high - time_low).total_seconds()

        slope = delta_y / delta_x if price_low != price_high else 0
        x_fwd = (current_time - time_low).total_seconds()

        return price_low + (x_fwd * slope)
