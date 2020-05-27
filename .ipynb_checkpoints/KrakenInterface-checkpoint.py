import pandas as pd
from bs4 import BeautifulSoup
import requests, re
import datetime


class KrakenInterface:

    def __init__(self, asset='ETH', currency='USD'):
        def get_assets_names():
            url = 'https://support.kraken.com/hc/en-us/articles/201893658-Currency-pairs-available-for-trading-on-Kraken'
            page = requests.get(url)
            soup = BeautifulSoup(page.text, "lxml")
            page.close()
            tbody = str(soup.find_all('tbody'))
            asset_names = re.findall(r'<td>(\w+\s*\w*)</td>\s*<td><strong>(.*)</strong></td>', tbody)
            return pd.DataFrame(asset_names, columns=['name', 'codes']).set_index('name').drop_duplicates().sort_index()

        if get_assets_names().codes.isin([asset]).any():
            self.asset = asset
        else:
            print('Please choose asset code name from the list: \n{}'.format(get_assets_names()))
            raise AttributeError('Invalid asset name.')
        self.currency = currency
        self.base = 'https://api.kraken.com/0/public'

    def order_book_of(self, count=7):
        '''Returns asks and bids as dataframes'''
        market = self.asset + self.currency
        url = self.base + '/Depth?pair={}&count={}'.format(market.upper(), count)
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
        url = self.base + '/OHLC?pair={}&interval={}&since={}' \
            .format(market.upper(), interval, since)
        marketS = 'X{}Z{}'.format(self.asset.upper(), self.currency.upper())

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
        url = self.base + '/Time'
        jsonData = requests.get(url).json()
        return datetime.datetime.fromtimestamp(jsonData["result"]["unixtime"])
