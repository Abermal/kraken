import json
import logging
import requests
import sched
import time
from datetime import timedelta
from KrakenInterface import KrakenInterface as KI

# logging.basicConfig(filename='priceChangeLog.txt', level=logging.INFO,
#                     format=' %(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.DEBUG,
                    format='(%(threadName)-10s) %(message)s')

logging.debug('Starting')
print("\nStarting tracking")

with open("token.json", 'r') as token_file:
    TOKEN = json.load(token_file)["TOKEN"]

with open("token.json", 'r') as token_file:
    CHAT_ID = json.load(token_file)["CHAT_ID"]

with open("config.json", 'r') as config_file:
    config = json.load(config_file)

BASE_URL = 'https://www.kogan.com/nz/'
TELEGRAM_API_SEND_MSG = f'https://api.telegram.org/bot{TOKEN}/sendMessage'

# THESE VARIABLES SHOULD BE RECIEVED FROM bot.py
step: int = 10
print(config)
asset = config["asset"]
currency = config["currency"]
period = 60

scheduler = sched.scheduler(time.time, time.sleep)
kr = KI(asset=asset, currency=currency)


def roundpr(price):
    return round(float(price), 2)

def time_formatter(time):
    if time < 60:
        msg = f"{int(time)}"
    elif time < 3600:
        s = time%60
        s_str = " s." if s > 0 else ""
        s = s if s > 0 else ""
        msg = f"{time//60}m. {s}{s_str}"
    elif time < 24 * 3600:
        h = time // 3600
        m = (time - 3600 * h)
        m_str = " m." if m > 0 else ""
        s = (time - h * 3600 - m * 60)
        s_str = " s." if s > 0 else ""
        m = m if m > 0 else ""
        s = s if s > 0 else ""
        msg = f"{h}h. {m}{m_str} {s}{s_str}"
    else:
        raise ValueError(f"time should be <= {24*60*60}.")
    return msg


msg = f"Tracker for {asset}({currency}) is activated.\nTracking step: {step}." \
      f"\nTracking interval: {time_formatter(period)}"
TELEGRAM_API_SEND_MSG = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}"
requests.post(TELEGRAM_API_SEND_MSG, data=msg)


oldprice = kr.get_current_price()
oldtime = time.perf_counter()


def check(oldprice: float):
    global step, asset, currency, oldtime

    left = oldprice // step * step
    right = left + step
    price = kr.get_current_price()

    if price > right or price < left:
        newtime = time.perf_counter()
        timeperiod = round(newtime - oldtime)
        oldtime = newtime

        text = '*{}* {} | previous: {} | period: {}' \
            .format(roundpr(price), currency, roundpr(oldprice), str(timedelta(seconds=timeperiod)))
        logging.info(text)

        oldprice = price
        data = {
            'chat_id': CHAT_ID,
            'text': text,
            'parse_mode': 'Markdown'}

        TELEGRAM_API_SEND_MSG = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}"
        r = requests.post(TELEGRAM_API_SEND_MSG, data=data)

    scheduler.enter(period, 1, check, argument=(oldprice,))


scheduler.enter(period, 1, check, argument=(oldprice,))
scheduler.run()
