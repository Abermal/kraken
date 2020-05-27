import requests
from KrakenInterface import KrakenInterface as KI
import sched, time
import logging

logging.basicConfig(level=logging.DEBUG, format=' %(asctime)s - %(levelname)s - %(message)s')

BASE_URL = 'https://www.kogan.com/nz/'
TOKEN = '1099662762:AAF7N5qKUo9y_ALvThyakYacrXuIlTrjY5o'
CHAT_ID = 256498289
TELEGRAM_API_SEND_MSG = f'https://api.telegram.org/bot{TOKEN}/sendMessage'

# THESE VARIABLES SHOULD BE RECIEVED FROM bot.py
step = 10
asset = "XBT"
currency = "EUR"
period = 1

s = sched.scheduler(time.time, time.sleep)
kr = KI(asset=asset, currency=currency)

oldprice = kr.get_current_price()

# TODO: add interval tracking
def check(oldprice):
    global step, asset, currency

    left = oldprice // step * step
    right = left + step
    price = kr.get_current_price()

    if price > right or price < left:
        logging.debug(f'\nPrice changed: {price}\n')
        oldprice = price
        text = '*{}*'.format(round(float(price), 2))
        data = {
            'chat_id': CHAT_ID,
            'text': text,
            'parse_mode': 'Markdown'
        }
        TELEGRAM_API_SEND_MSG = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}"
        # TELEGRAM_API_SEND_MSG = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={text}"
        # logging.debug(TELEGRAM_API_SEND_MSG)

        r = requests.post(TELEGRAM_API_SEND_MSG, data=data)


    s.enter(period, 1, check, argument=(oldprice,))


s.enter(period, 1, check, argument=(oldprice,))
s.run()
