import telebot as tlg
from telebot import types
import json
import logging
import time
import os
import requests
import functools
from flask import Flask, request
from datetime import timedelta
from multiprocessing import Process, Event
from KrakenInterface import KrakenInterface as KI
from utils import *

logging.basicConfig(level=logging.INFO,
                    format=' %(asctime)s - %(processName)s - %(funcName)10s - %(message)s')

TOKEN = os.getenv("TOKEN")
logger = logging.getLogger("BOT_log")


class User:
    def __init__(self, asset='XBT', currency='EUR'):
        self.user_data = {}
        self.asset = asset
        self.currency = currency
        self.uid = None
        self.cid = None
        self.help = False
        self.step = 100
        self.period = 1
        self.tracking = False

    def __setattr__(self, key, value):
        if key != "user_data":
            self.__dict__[key] = value
            self.user_data[key] = value

            with open("../config.json", "w+") as json_file:
                json.dump(self.user_data, json_file)
                logger.info(f"{key}: {value}")
        else:
            self.__dict__[key] = value

    def update(self, config):
        self.user_data = config
        for atr in self.__dict__:
            if atr != "user_data":
                self.__dict__[atr] = config[atr]
            else:
                pass

# Initialize objects
logger.info(__name__)
bot = tlg.TeleBot(TOKEN)
user = User()
kr = KI()

# Set parameters for keyboards
menu_commands = ['Set asset', 'Set currency', 'List assets', 'Current price', 'Track price']
intervals = ['1', '60', '600', '3600', 'Another interval']
interval_names = [format_interval_name(interval) for interval in intervals]
steps = ['10', '50', '100', '200']
sufix = " c.u."

# Logging decorator
def log_message(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        message = args[0]
        logger.info(message)
        try:
            logger.info(message.text)
        except AttributeError:
            pass
        return func(*args, **kwargs)
    return wrapper


# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
# Start command containing 3 buttons
@bot.message_handler(commands=['start'])
@log_message
def start_message(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.row(*menu_commands)

    asset_name = kr.get_full_name(user.asset)
    currency_name = kr.get_full_name(user.currency)

    greeting = f"Hi {message.chat.first_name}!\n" \
               f"I can show you the current price for various cryptocurrencies and " \
               f"help you to track the price with a given step." \
               f"\n(Default: {user.asset}|{asset_name} in {user.currency}|{currency_name})\n\n"

    user.cid = message.chat.id
    bot.send_message(message.chat.id, reply_markup=keyboard,
                     text=greeting + f"Select one of the options:")
# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
# "Set asset" button containing 3 buttons
@bot.message_handler(commands=['asset'])
@bot.message_handler(func=lambda mess: menu_commands[0] == mess.text)  # 'Set asset'
@log_message
def markup_asset(message):
    assets_markup = types.InlineKeyboardMarkup(row_width=2)
    XBT = types.InlineKeyboardButton("XBT", callback_data='XBT')
    ETH = types.InlineKeyboardButton("ETH", callback_data='ETH')
    ANOTHER = types.InlineKeyboardButton("Another", callback_data='Another')
    assets_markup.add(XBT, ETH, ANOTHER)
    bot.send_message(message.chat.id, "Select your asset (Cryptocurrency):", reply_markup=assets_markup)


# "Specific asset choice"-button press handler
@bot.callback_query_handler(
    func=lambda call: call.data == 'XBT' or call.data == 'ETH' or call.data == 'Another')
def callback_asset(call):
    try:
        if call.data == 'XBT' or call.data == 'ETH':
            user.uid = call.message.chat.id
            user.asset = call.data
            bot.send_message(call.message.chat.id,
                             f"{user.asset}|{kr.get_full_name(user.asset)} selected.")
            markup_current_price(call.message)

        elif call.data == 'Another':
            bot.send_message(call.message.chat.id,
                             "Please type in asset code.\nTo see full list press /help")
            bot.register_next_step_handler(call.message, set_custom_asset)

    except Exception as e:
        print(repr(e))


# Function to check if asset name is correct
@log_message
def set_custom_asset(message):
    asset = message.text

    if kr.check_asset(asset):
        user.asset = message.text.upper()
        bot.send_message(message.chat.id, f"{user.asset}|{kr.get_full_name(user.asset)} selected.")
        markup_current_price(message)

    elif asset == '/HELP':
        user.help = True
        help_message(message)
    elif asset in menu_commands[0]:
        markup_asset(message)
    elif asset == menu_commands[1]:
        markup_currency(message)
    elif asset == menu_commands[2]:
        help_message(message)
    elif asset == menu_commands[3]:
        markup_current_price(message)
    elif asset == menu_commands[4]:
        markup_track_price(message)
    else:
        bot.send_message(message.chat.id,
                         f"{asset} is not a valid asset code. Please press /help.")
        time.sleep(5)
        bot.register_next_step_handler(message, set_custom_asset)
# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
@bot.message_handler(commands=['currency'])
@bot.message_handler(func=lambda mess: mess.text == menu_commands[1])  # 'Set currency'
@log_message
def markup_currency(message):
    currency_markup = types.InlineKeyboardMarkup(row_width=2)
    currency_markup.add(*[types.InlineKeyboardButton(fiat, callback_data=fiat) for fiat in
                          kr.fiats.codes_clean.values])
    bot.send_message(message.chat.id, 'Select your currency:', reply_markup=currency_markup)


@bot.callback_query_handler(func=lambda call: call.data in kr.fiats.codes_clean.values)
def callback_currency(call):
    user.currency = call.data
    bot.send_message(call.message.chat.id,
                     f"{user.currency}|{kr.get_full_name(user.currency)} selected.")

    markup_current_price(call.message)
# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
@bot.message_handler(func=lambda mess: mess.text in kr.fiats.codes_clean.values)
@bot.message_handler(func=lambda mess: mess.text == menu_commands[3])  # 'Current price'
@log_message
def markup_current_price(message):
    current_price_markup = types.InlineKeyboardMarkup()
    current_price = types.InlineKeyboardButton("Show current price",
                                               callback_data='current_price')
    current_price_markup.add(current_price)
    bot.send_message(message.chat.id, 'Press button to show current price',
                     reply_markup=current_price_markup)


@bot.callback_query_handler(func=lambda call: call.data == 'current_price')
def callback_current_price(call):
    kraken = KI(asset=user.asset, currency=user.currency)
    asset_name = kraken.get_full_name(user.asset)
    currency_name = kraken.get_full_name(user.currency)
    try:
        price = kraken.get_current_price()
        logger.info("Price was sent.")
        bot.send_message(call.message.chat.id, parse_mode='MarkDown',
                         text=f"Current {user.asset}|{asset_name} price in {user.currency}|{currency_name} is: ***{price:.5f}***")

    except Exception as e:
        if e == ValueError:
            print(e)
            valid_quotes = kraken.find_valid_quotes()
            bot.send_message(call.message.chat.id,
                             f"Invalid AssetPair. Valid quotes for {user.asset}|{asset_name} base are:"
                             f"\n{format_codes_names(valid_quotes)}")
        start_message(call.message)
# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
@bot.message_handler(func=lambda mess: mess.text == menu_commands[2])  # 'List assets'
@bot.message_handler(commands=['help'])
@log_message
def help_message(message):
    bot.send_message(message.from_user.id, parse_mode='MarkDown',
                     text=f"Valid assets are: \n```\n{format_codes_names(kr.assets)}\n```")
    if user.help:
        user.help = False
        bot.register_next_step_handler(message, set_custom_asset)
# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
@bot.message_handler(func=lambda mess: mess.text == 'Track price')
@log_message
def markup_track_price(message):
    user.cid = message.chat.id
    track_price_markup = types.InlineKeyboardMarkup(row_width=2)
    STEP = types.InlineKeyboardButton("Set price step", callback_data='step')
    INTERVAL = types.InlineKeyboardButton("Set time interval in seconds",
                                          callback_data='interval')
    TRACK = types.InlineKeyboardButton(text='Track', callback_data='Start')
    track_price_markup.add(STEP, INTERVAL, TRACK)
    bot.send_message(message.chat.id, 'Select tracking parameters:',
                     reply_markup=track_price_markup)


@bot.callback_query_handler(func=lambda call: call.data == 'step' or call.data == 'interval')
def callback_track_price(call):
    if call.data == 'step':
        markup_step(call.message)
    elif call.data == 'interval':
        markup_interval(call.message)
# ----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
@bot.message_handler(commands=['step'])
@log_message
def markup_step(message):
    step_markup = types.InlineKeyboardMarkup(row_width=2)
    step_markup.add(*[types.InlineKeyboardButton(step + sufix, callback_data=step + sufix) for step in steps])
    CUSTOM = types.InlineKeyboardButton("Another step", callback_data="Another step")
    step_markup.add(CUSTOM)
    bot.send_message(message.chat.id, "Select your tracking step in common units(c.u.):",
                     reply_markup=step_markup)


@bot.callback_query_handler(func=lambda call: call.data in [step + sufix for step in steps])
def callback_step(call):
    user.step = float(call.data.rstrip(sufix))
    bot.send_message(call.message.chat.id,
                     f"{user.step} {user.currency} selected as tracking step.")
    if not user.period:
        markup_interval(call.message)
    else:
        markup_track(call.message)


@bot.callback_query_handler(func=lambda call: call.data == "Another step")
def callback_custom_step(call):
    bot.send_message(call.message.chat.id, "Please type in step in common units.")
    bot.register_next_step_handler(call.message, set_custom_step)


@log_message
def set_custom_step(message):
    try:
        step = float(message.text)
        if step < 0:
            raise ValueError
        user.step = step
    except ValueError:
        bot.send_message(message.chat.id, f"Step should be a positive number.")
        time.sleep(5)
        bot.register_next_step_handler(message, set_custom_step)
    else:
        bot.send_message(message.chat.id, f"{user.step} selected as tracking step.")
    if not user.period:
        markup_interval(message)
    else:
        markup_track(message)


# ----------------------------------------------------------------------------------------------------------------------
@bot.message_handler(commands=['step'])
@log_message
def markup_step(message):
    step_markup = types.InlineKeyboardMarkup(row_width=3)
    step_markup.add(*[types.InlineKeyboardButton(step + sufix, callback_data=step + sufix) for step in steps])
    CUSTOM = types.InlineKeyboardButton("Another", callback_data="Another step")
    step_markup.add(CUSTOM)
    bot.send_message(message.chat.id, "Select your tracking step in common units(c.u.):",
                     reply_markup=step_markup)


# ----------------------------------------------------------------------------------------------------------------------
@bot.message_handler(commands=['interval'])
@log_message
def markup_interval(message):
    interval_markup = types.InlineKeyboardMarkup()
    interval_markup.add(*[types.InlineKeyboardButton(interval, callback_data=interval) for interval in interval_names])
    bot.send_message(message.chat.id, "Select your tracking interval:",
                     reply_markup=interval_markup)


@bot.callback_query_handler(func=lambda call: call.data in ["60", "600", "3600"])
def callback_interval(call):
    user.period = int(call.data)
    bot.send_message(call.message.chat.id,
                     f"{format_time(user.period)} selected as tracking interval.")
    if not user.period:
        markup_interval(call.message)
    else:
        markup_track(call.message)


@bot.callback_query_handler(func=lambda call: call.data == "Another interval")
def callback_custom_interval(call):
    bot.send_message(call.message.chat.id, "Please type in interval in seconds.")
    bot.register_next_step_handler(call.message, set_custom_interval)


@log_message
def set_custom_interval(message):
    try:
        user.period = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, f"Interval should be a positive integer.")
        time.sleep(5)
        bot.register_next_step_handler(message, set_custom_interval)
    else:
        bot.send_message(message.chat.id, f"{format_time(user.period)} selected")
    if not user.step:
        markup_step(message)
    else:
        markup_track(message)
# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
@log_message
def markup_track(message):
    track_markup = types.InlineKeyboardMarkup()
    START = types.InlineKeyboardButton(text='Start', callback_data='Start')
    STOP = types.InlineKeyboardButton(text='Stop', callback_data='Stop')
    track_markup.add(START, STOP)
    if not user.tracking:
        msg = "To start tracking press 'Start':"
    else:
        msg = "To stop tracking press 'Stop'"
    bot.send_message(message.chat.id, msg, reply_markup=track_markup)

# TODO Check if user has already an ongoing tracking
@bot.callback_query_handler(func=lambda call: call.data == "Start")
def callback_track(call):
    if __name__ == '__main__':
        global tracker
        event.clear()
        user.tracking = True
        tracker = Process(target=track_price, args=(user.user_data, event))
        tracker.start()

        print('\nAlive?:', tracker.is_alive())
        print(tracker.pid, '\n')
        markup_track(call.message)


@bot.callback_query_handler(func=lambda call: call.data == "Stop")
def callback_stop(call):
    event.set()
    tracker.join()
    bot.send_message(call.message.chat.id, "Tracking stopped")
    print('\nTracker alive?:', tracker.is_alive())
    print(tracker.pid, '\n')
    user.tracking = False


# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
def track_price(config, event):
    logger.info('Starting tracking')
    logger.info(config)

    step: int = config["step"]
    asset = config["asset"]
    currency = config["currency"]
    period = config["period"]
    cid = config["cid"]

    kraken = KI(asset=asset, currency=currency)
    asset_name = kraken.get_full_name(asset)
    currency_name = kraken.get_full_name(currency)

    # Этот кусок работает, но с переменными тут явно путанина
    old_price = roundpr(kraken.get_current_price())
    old_time = time.perf_counter()

    msg = f"Tracker for {asset}|{asset_name} price in {currency}|{currency_name} is activated." \
          f"\nTracking step: {step}." \
          f"\nTracking interval: {format_time(period)}" \
          f"\nStarting point: {old_price}"
    TELEGRAM_API_SEND_MSG = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={cid}"
    data_start = {'chat_id': cid, 'text': msg, 'parse_mode': 'Markdown'}
    requests.post(TELEGRAM_API_SEND_MSG, data=data_start)

    def check(old_price, old_time):
        center = round_clip(old_price, step)
        left = center - step
        right = center + step
        price = kraken.get_current_price()

        up = price > right
        down = price < left
        if up or down:
            new_time = time.perf_counter()
            time_period = round(new_time - old_time)
            if up:
                up_arrow = ' ⬆️ '
                direction = ' *UP*' + up_arrow
            elif down:
                down_arrow = ' ⬇️'
                direction = ' *DOWN*' + down_arrow

            text = '*{}* {} | previous: {} | \nstep: {} | period: {}' \
                .format(round_clip(price, step), currency, round_clip(old_price, step), step, str(timedelta(seconds=time_period)))
            text += direction
            logging.info(text)
            data = {
                'chat_id': cid,
                'text': text,
                'parse_mode': 'Markdown'}
            TELEGRAM_API_SEND_MSG = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={cid}"

            requests.post(TELEGRAM_API_SEND_MSG, data=data)

            old_time = new_time
            old_price = price

        return old_price, old_time

    while True:
        old_price, old_time = check(old_price, old_time)
        time.sleep(period)

        even_status = f'IS event set? {event.is_set()}'
        logger.info(even_status)

        if event.is_set():
            break


if "HEROKU_URL" in list(os.environ.keys()):
    if __name__ == "__main__":
        server = Flask(__name__)


        @server.route('/' + TOKEN, methods=['POST'])
        def get_message():
            bot.process_new_updates(
                [types.Update.de_json(request.stream.read().decode("utf-8"))])
            return "!", 200


        @server.route("/")
        def web_hook():
            bot.remove_webhook()
            bot.set_webhook(url=os.getenv('HEROKU_URL') + TOKEN)
            return "!", 200


        event = Event()
        server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8443)), debug=True)

else:
    if __name__ == '__main__':
        try:
            bot.remove_webhook()
        except:
            pass
        event = Event()
        bot.polling(none_stop=True, interval=0)

# kraken-hourly-bid-bot
# heroku container:login
# heroku container:push web --app kraken-hourly-bid-bot
# heroku container:release web --app kraken-hourly-bid-bot
# heroku logs --tail --app kraken-hourly-bid-bot


# heroku ps:scale web=0 -a kraken-hourly-bid-bot
# -a kraken-hourly-bid-bot
# heroku config --app kraken-hourly-bid-bot
