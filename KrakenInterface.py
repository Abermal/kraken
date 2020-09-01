import pandas as pd
from bs4 import BeautifulSoup
import requests, re
import datetime
import codecs


def print_code_name(df):
    s = ''
    for key, val in zip(df.codes.values, df.name.values):
        s += '{:<4s} | {:s}\n'.format(str(key), str(val))
    return s

class KrakenInterface:

    def __init__(self, asset='XBT', currency='EUR'):

        self.asset_names = self.get_asset_names().name.values
        self.asset_codes = self.get_asset_names().codes.values
        self.fiat_codes = self.get_fiat_names().codes.values

        if asset.upper() in self.asset_codes or "X" + asset.upper() in self.asset_codes\
                and "Z" + currency.upper() in self.fiat_codes:
            self.asset = asset.upper()
            self.currency = currency.upper()
        else:
            print('Please choose asset code name from the list: \n{}' \
                  .format(print_code_name(self.get_asset_names())))
            raise AttributeError('Invalid asset name.')

        self.base = 'https://api.kraken.com/0/public/'
        self.crypto_names = print_code_name(self.get_crypto_for_fiat())

    def get_asset_names(self):
        # url = 'https://support.kraken.com/hc/en-us/articles/201893658-Currency-pairs-available-for-trading-on-Kraken'

        page = open('curr_names.html', 'r').read()
        soup = BeautifulSoup(page, "lxml")
        tbody = str(soup.find('tbody'))
        asset_names = re.findall('<tr>\n<td class="confluenceTd">(\w*)</td>\n<td class="confluenceTd">(.*)</td>', tbody)
        asset_names = pd.DataFrame(asset_names, columns=['codes', 'name'])
        return asset_names

    def get_fiat_names(self):
        asset_names = self.get_asset_names()
        return asset_names[asset_names.codes.str.startswith('Z')]

    def get_crypto_names(self):
        asset_names = self.get_asset_names()
        return asset_names[~asset_names.codes.str.startswith('Z')]

    def get_asset_pairs(self):
        """ altname = alternate pair name
            wsname = WebSocket pair name (if available)
            aclass_base = asset class of base component
            base = asset id of base component
            aclass_quote = asset class of quote component
            quote = asset id of quote component"""

        url = self.base + 'AssetPairs'
        page = requests.get(url)
        jString = page.json()
        return pd.DataFrame(jString["result"]).T.iloc[:, :6]

    def get_fiat_pairs(self):
        allpairs = self.get_asset_pairs()
        fiats = [x for x in allpairs.quote.unique() if x[0] == "Z"]
        fiatmask = allpairs['quote'].isin(fiats)
        return allpairs[fiatmask]

    def get_crypto_for_fiat(self):
        asset_names = self.get_asset_names()
        cryptofiat = self.get_fiat_pairs().base.unique()
        return asset_names[asset_names.codes.isin(cryptofiat)]

    def get_current_price(self):
        return self.order_book_of(1)[0].price.iloc[-1]

    def order_book_of(self, count=7):
        '''Returns asks and bids as dataframes'''
        market = self.asset + self.currency
        url = self.base + 'Depth?pair={}&count={}'.format(market.upper(), count)
        marketS = 'X{}Z{}'.format(self.asset.upper(), self.currency.upper())

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
        '''Returns OHLC data representation as df
        interval = time frame interval in minutes (optional):
                1 (default), 5, 15, 30, 60, 240, 1440, 10080, 21600
        since = return committed OHLC data since given id (optional.  exclusive)'''
        # input check
        interval_values = [1, 5, 15, 30, 60, 240, 1440, 10080, 21600]
        if interval not in interval_values:
            raise AttributeError(
                '\ntime frame interval in minutes (optional): 1 (default), 5, 15, 30, 60, 240, 1440, 10080, 21600')

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


# kr = KrakenInterface()
# print(kr.get_asset_names())

