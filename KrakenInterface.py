import datetime
import numpy as np
import pandas as pd
import re
import requests
from bs4 import BeautifulSoup


def format_codes_names(df, column="codes_clean"):
    s = ''
    max_len = df[column].str.len().max()
    for key, val in zip(df[column].values, df.name.values):
        s += f'{str(key):<{max_len}s} | {str(val):s}\n'
    return s


class KrakenInterface:
    def __init__(self, asset='XBT', currency='EUR'):
        self.base = 'https://api.kraken.com/0/public/'
        self.assets = self.get_asset_names()
        self.asset_codes = self.assets["codes"].values
        self.fiats = self.assets[self.assets["fiats"].notna()]
        self.fiat_codes = self.assets["fiats"].dropna().values
        self.asset = asset.upper()
        self.currency = currency.upper()
        self.asset = asset.upper()
        self.currency = currency.upper()
        self.asset_pairs = self.get_asset_pairs()
        # if currency.upper()[0] != "Z" else "Z" + currency.upper()

        # self.crypto_names = print_codes_names(self.get_crypto_for_fiat(), "")

    @property
    def asset(self):
        return self._asset

    @asset.setter
    def asset(self, value):
        if self.check_asset(value):
            self._asset = value
        else:
            raise AttributeError(f'Invalid asset name {self._asset}. Please choose asset code name from the list: '
                                 f'\n{format_codes_names(self.assets)}')

    @property
    def currency(self):
        return self._currency

    @currency.setter
    def currency(self, value):
        if self.check_currency(value):
            self._currency = value
        else:
            raise AttributeError(f'Invalid currency name. Please choose currency code name from the list: '
                                 f'\n{format_codes_names(self.fiats)}')

    def check_asset(self, asset):
        return asset.upper() in self.asset_codes or asset.upper() in self.assets["codes_clean"].values

    def check_currency(self, currency):
        return currency.upper() in self.fiat_codes or currency.upper() in ("Z" + self.fiat_codes)

    def get_full_name(self, code: str) -> str:
        if self.check_asset(code) or self.check_currency(code):
            return self.assets.query("codes_clean == @code").name.values[0]
        else:
            value_name = "currency" if self.check_currency(code) else "asset"
            info = self.fiats if self.check_currency(code) else self.assets
            raise AttributeError(f'Invalid {value_name} name. Please choose {value_name} code name from the list: '
                                 f'\n{format_codes_names(info)}')

    def get_asset_names(self) -> pd.DataFrame:
        # url = 'https://support.kraken.com/hc/en-us/articles/201893658-Currency-pairs-available-for-trading-on-Kraken'
        page = open('curr_names.html', 'r').read()
        soup = BeautifulSoup(page, "lxml")
        table = soup.findAll("td")[4:]

        codenames = {}
        for code, name, status in zip(table[::4], table[1::4], table[3::4]):
            if status.contents[0] == '\xa0':
                if code.span is None:
                    codenames[code.contents[0]] = name.contents[0]
                else:
                    codenames[code.span.contents[0]] = re.findall("[\w\s]+", name.span.contents[0])[0]

        #     print(f"{code.contents[0]}: {name.contents[0]}")
        # codes_clean = ass.code.apply(lambda x: x[1:] if (x[0] == "X")|(x[0] == "Z") else x)

        asset_names = pd.DataFrame(data=codenames.items(), columns=['codes', 'name'])
        asset_names["codes_clean"] = asset_names["codes"].apply(lambda x: x[1:] if (x[0] == "X") | (x[0] == "Z") else x)
        asset_names["fiats"] = asset_names["codes"].apply(lambda x: x[1:] if x[0] == 'Z' else np.nan)
        asset_names["cryptos"] = asset_names[asset_names["fiats"].isna()]["codes_clean"]
        return asset_names

    def get_asset_pairs(self) -> pd.DataFrame:
        """ altname = alternate pair name
            wsname = WebSocket pair name (if available)
            aclass_base = asset class of base component
            base = asset id of base component
            aclass_quote = asset class of quote component
            quote = asset id of quote component"""

        url = self.base + 'AssetPairs'
        page = requests.get(url)
        jString = page.json()
        asset_pairs = pd.DataFrame(jString["result"]).T.iloc[:, :6]
        asset_pairs[["base_clean", "quote_clean"]] = asset_pairs["wsname"].str.split("/", expand=True)
        return asset_pairs

    def find_index(self, asset=None, currency=None):
        if asset is None:
            asset = self.asset
        if currency is None:
            currency = self.currency

        try:
            return self.asset_pairs.query("base_clean == @asset.upper() & quote_clean == @currency.upper()").index[0]
        except IndexError as e:
            valid_quotes_df = self.find_valid_quotes(asset)
            raise ValueError(f"Invalid AssetPair. Valid quotes for {asset} base are:"
                             f"\n{format_codes_names(valid_quotes_df)}")

    def find_valid_quotes(self, asset: str = None) -> pd.DataFrame:
        """Returns dataframe with quotes (currencies) available for this asset."""
        if asset is None:
            asset = self.asset

        valid_quotes = self.asset_pairs.query("base_clean == @asset.upper()")["quote_clean"].values
        return self.assets[self.assets["codes_clean"].isin(valid_quotes)]

    def get_fiat_pairs(self) -> pd.DataFrame:
        return self.asset_pairs[self.asset_pairs["quote_clean"].isin(self.fiat_codes)]

    def get_crypto_names_for_fiat(self):
        """delete?"""
        crypto_for_fiat = self.get_fiat_pairs().base.unique()
        return self.assets[self.assets.codes.isin(crypto_for_fiat)]

    def get_current_price(self):
        return self.order_book_of(1)[0].price.iloc[-1]

    def order_book_of(self, count=7):
        """Returns asks and bids as dataframes."""
        market = self.asset + self.currency
        url = self.base + 'Depth?pair={}&count={}'.format(market.upper(), count)
        marketS = self.find_index()

        page = requests.get(url)
        jString = page.json()
        asks = jString["result"][marketS]["asks"]
        bids = jString["result"][marketS]["bids"]

        dataAsks = pd.DataFrame(asks, columns=['price', 'volume', 'timestamp'], dtype='float32')
        dataBids = pd.DataFrame(bids, columns=['price', 'volume', 'timestamp'], dtype='float32')

        dataAsks['timestamp'] = [datetime.datetime.fromtimestamp(d) for d in dataAsks.timestamp]
        dataBids['timestamp'] = [datetime.datetime.fromtimestamp(d) for d in dataBids.timestamp]

        return dataAsks, dataBids

    def ohlc_data_of(self, interval=1, since=None, print_url=False):
        """Returns OHLC data representation as df
        interval = time frame interval in minutes (optional):
                1 (default), 5, 15, 30, 60, 240, 1440, 10080, 21600
        since = return committed OHLC data since given id (optional.  exclusive)"""
        # input check
        interval_values = [1, 5, 15, 30, 60, 240, 1440, 10080, 21600]
        if interval not in interval_values:
            raise AttributeError('\ntime frame interval in minutes (optional): 1 (default), 5, 15, 30, 60, 240, 1440, 10080, 21600')

        market = self.asset + self.currency
        url = self.base + 'OHLC?pair={}&interval={}&since={}' \
            .format(market.upper(), interval, since)
        marketS = '{}{}'.format(self.asset.upper(), self.currency.upper())

        if print_url:
            print(url)
        jsonFile = requests.get(url).json()
        data = pd.DataFrame(jsonFile["result"][marketS],
                            columns=['time', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'],
                            dtype='float32')
        data['time'] = [datetime.datetime.fromtimestamp(d) for d in data.time]
        data.set_index('time', inplace=True)
        return data

    def server_time(self):
        url = self.base + 'Time'
        jsonData = requests.get(url).json()
        return datetime.datetime.fromtimestamp(jsonData["result"]["unixtime"])


# kr = KrakenInterface("XTZ", "usd")
# asset_name = kr.get_full_name("XBT")
# print(kr.assets)
# print(format_codes_names(kr.assets))
# print(format_codes_names(kr.find_valid_quotes("XTZ")))
# print(kr.get_current_price())
