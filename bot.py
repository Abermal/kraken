import telebot as tlg
from telebot import types
from KrakenInterface import KrakenInterface as KI
from multiprocessing import Process
import  multiprocessing as mp
import logging
import time, json

with open("token.json", 'r') as token_file:
    TOKEN = json.load(token_file)["TOKEN"]


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


class User:
    def __init__(self, asset='XBT', currency='EUR'):
        self.user_data = {}
        self.asset = asset
        self.currency = currency
        self.state = 0
        self.uid = None
        self.help = False
        self.step = 10
        self.period = 1
        self.tracking = False

    def __setattr__(self, key, value):
        if key != "user_data":
            self.__dict__[key] = value
            self.user_data[key] = value

            filename = "config.json"
            with open(filename, "w+") as json_file:
                json.dump(self.user_data, json_file)
                print(f"{key}: {value}")
        else:
            self.__dict__[key] = value


bot = tlg.TeleBot(TOKEN)
user = User()
kr = KI()

# TODO clear history and restart bot on new run

# ----------------------------------------------------------------------------------------------------------------------
# Start command containing 3 buttons
@bot.message_handler(commands=['start'])
def start_message(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.row('1 | Set asset', '2 | Set currency', '3 | List assets', '4 | Show price', '5 | Track price')
    greeting = ''
    if user.state == 0:
        greeting = f"Hi {message.chat.first_name}!\n"

    bot.send_message(message.chat.id,
                     text= greeting + f"Select one of options", reply_markup=keyboard)
# ----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# "Set asset" button containing 3 buttons
@bot.message_handler(commands=['asset'])
@bot.message_handler(func=lambda mess: '1 | Set asset' == mess.text or mess.text == '1')
def markup_asset(message):
    assets_markup = types.InlineKeyboardMarkup(row_width=2)
    XBT = types.InlineKeyboardButton("XBT", callback_data='XBT')
    ETH = types.InlineKeyboardButton("ETH", callback_data='ETH')
    ANOTHER = types.InlineKeyboardButton("Another", callback_data='Another')
    assets_markup.add(XBT, ETH, ANOTHER)
    bot.send_message(message.chat.id, "Select your asset:", reply_markup=assets_markup) # changed to message.chat.id

# "Specific asset choice"-button press handler
@bot.callback_query_handler(func=lambda call: call.data == 'XBT' or call.data == 'ETH' or call.data == 'Another')
def callback_asset(call):
    try:
        if call.data == 'XBT' or call.data == 'ETH':
            user.uid = call.message.chat.id
            user.asset = call.data
            user.state += 1

            bot.send_message(call.message.chat.id, "{} selected".format(user.asset))

            if user.state == 1:
                markup_currency(call.message)
            else:
                markup_current_price(call.message)

        elif call.data == 'Another':
            bot.send_message(call.message.chat.id, "Please type in asset code.\nTo see full list press /help")
            bot.register_next_step_handler(call.message, set_custom_asset)

    except Exception as e:
        print(repr(e))


# Function to check if asset name is correct
def set_custom_asset(message):
    asset = message.text.upper()

    if asset in kr.asset_codes:
        user.asset = message.text.upper()
        user.state += 1
        bot.send_message(message.chat.id, "{} selected".format(user.asset))

        if user.state == 1:
            markup_currency(message)
        else:
            markup_current_price(message)

    elif asset == '/HELP':
        user.help = True
        help_message(message)

    else:
        bot.send_message(message.chat.id, "{} is not valid. Please press /help.".format(asset))
        time.sleep(5)
        bot.register_next_step_handler(message, set_custom_asset)
# ----------------------------------------------------------------------------------------------------------------------



# ----------------------------------------------------------------------------------------------------------------------
@bot.message_handler(func=lambda mess: mess.text == '2 | Set currency' or mess.text == '2')
def markup_currency(message):
    currency_markup = types.InlineKeyboardMarkup(row_width=2)
    USD = types.InlineKeyboardButton("USD", callback_data='USD')
    EUR = types.InlineKeyboardButton("EUR", callback_data='EUR')
    currency_markup.add(USD, EUR)
    bot.send_message(message.chat.id, 'Select your currency:', reply_markup=currency_markup)


@bot.callback_query_handler(func=lambda call: call.data == 'USD' or call.data == 'EUR')
def callback_currency(call):
    user.currency = call.data
    user.state += 1
    bot.send_message(call.message.chat.id, "{} selected".format(user.currency))

    if user.state == 1:
        markup_asset(call.message)
    else:
        markup_current_price(call.message)
# ----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
@bot.message_handler(func=lambda mess: mess.text == 'USD' or mess.text == 'EUR')
@bot.message_handler(func=lambda mess: mess.text == '4 | Show price' or mess.text == '4')
def markup_current_price(message):
    current_price_markup = types.InlineKeyboardMarkup()
    current_price = types.InlineKeyboardButton("Show current price", callback_data='current_price')
    current_price_markup.add(current_price)
    bot.send_message(message.chat.id, 'Press button to show current price', reply_markup=current_price_markup)


@bot.callback_query_handler(func=lambda call: call.data == 'current_price')
def callback_current_price(call):
    user.state -= 1
    try:
        price = round(get_current_price(), 2)

    except Exception:
        bot.send_message(call.message.chat.id, 'Something went wrong, please choose USD or different asset.')
        user.state += 1
        start_message(call.message)

    else:
        bot.send_message(call.message.chat.id,
                         "Current {} price in {} is: ***{:.4f}***".format(user.asset, user.currency, price),
                         parse_mode='MarkDown')


def get_current_price():
    kr = KI(asset=user.asset, currency=user.currency)
    return kr.get_current_price()
# ----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
@bot.message_handler(func=lambda mess: mess.text == '3 | List assets' or mess.text == '3')
@bot.message_handler(commands=['help'])
def help_message(message):
    bot.send_message(message.from_user.id, "Valid assets are: \n```\n" + KI().crypto_names + "\n```",
                     parse_mode='MarkDown')
    if user.help:
        user.help = False
        bot.register_next_step_handler(message, set_custom_asset)
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
@bot.message_handler(func=lambda mess: mess.text == '5 | Track price' or mess.text == '5')
def markup_track_price(message):
    track_price_markup = types.InlineKeyboardMarkup(row_width=2)
    STEP = types.InlineKeyboardButton("Set price step", callback_data='step')
    INTERVAL = types.InlineKeyboardButton("Set time interval in seconds", callback_data='interval')
    TRACK = types.InlineKeyboardButton(text='Track', callback_data='Track')
    track_price_markup.add(STEP, INTERVAL, TRACK)
    bot.send_message(message.chat.id, 'Select tracking parameters:', reply_markup=track_price_markup)


@bot.message_handler(commands=['interval'])
def markup_interval(message):
    interval_markup = types.InlineKeyboardMarkup()
    ONEMIN = types.InlineKeyboardButton("1 min.", callback_data="60")
    TENMIN = types.InlineKeyboardButton("10 min", callback_data="600")
    ONEHOUR = types.InlineKeyboardButton("1 hour", callback_data="3600")
    CUSTOM = types.InlineKeyboardButton("Another", callback_data="Another interval")
    interval_markup.add(ONEMIN, TENMIN, ONEHOUR, CUSTOM)
    bot.send_message(message.chat.id, "Select your interval:", reply_markup=interval_markup)


@bot.message_handler(commands=['step'])
def markup_step(message):
    step_markup = types.InlineKeyboardMarkup(row_width=3)
    FIFTY = types.InlineKeyboardButton("50 c.u.", callback_data="50")
    HUNDRED = types.InlineKeyboardButton("100 c.u.", callback_data="100")
    CUSTOM = types.InlineKeyboardButton("Another", callback_data="Another step")
    step_markup.add(FIFTY, HUNDRED, CUSTOM)
    bot.send_message(message.chat.id, "Select your interval:", reply_markup=step_markup)


@bot.callback_query_handler(func=lambda call: call.data == 'step' or call.data == 'interval')
def callback_track_price(call):
    if call.data == 'step':
        markup_step(call.message)
    elif call.data == 'interval':
        markup_interval(call.message)


@bot.callback_query_handler(func=lambda call: call.data in ["50", "100"])
def callback_step(call):
    user.step = int(call.data)
    bot.send_message(call.message.chat.id, f"{user.step} c.u. selected")
    if not user.period:
        markup_interval(call.message)
    else:
        markup_track(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "Another step")
def callback_custom_interval(call):
    bot.send_message(call.message.chat.id, "Please type in step in common units.")
    bot.register_next_step_handler(call.message, set_custom_step)

def set_custom_step(message):
    try:
        user.step = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, f"Step should be a positive integer.")
        time.sleep(5)
        bot.register_next_step_handler(message, set_custom_step)
    else:
        bot.send_message(message.chat.id, "{} selected".format(user.step))
    if not user.period:
        markup_interval(message)
    else:
        markup_track(message)


@bot.callback_query_handler(func=lambda call: call.data in ["60", "600", "3600"])
def callback_interval(call):
    user.period = int(call.data)
    bot.send_message(call.message.chat.id, f"{time_formatter(user.period)} selected")
    if not user.period:
        markup_interval(call.message)
    else:
        markup_track(call.message)


@bot.callback_query_handler(func=lambda call: call.data == "Another interval")
def callback_custom_interval(call):
    bot.send_message(call.message.chat.id, "Please type in interval in seconds.")
    bot.register_next_step_handler(call.message, set_custom_interval)

def set_custom_interval(message):
    try:
        user.period = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, f"Interval should be a positive integer.")
        time.sleep(5)
        bot.register_next_step_handler(message, set_custom_interval)
    else:
        bot.send_message(message.chat.id, "{} selected".format(user.period))
    if not user.step:
        markup_step(message)
    else:
        markup_track(message)


def markup_track(message):
    track_markup = types.InlineKeyboardMarkup()
    TRACK = types.InlineKeyboardButton(text='Track', callback_data='Track')
    STOP = types.InlineKeyboardButton(text='Stop', callback_data='Stop')
    track_markup.add(TRACK, STOP)
    if not user.tracking:
        msg = "To start tracking press 'Start':"
    else:
        msg = "To stop tracking press 'Stop'"
    bot.send_message(message.chat.id, msg, reply_markup=track_markup)


def track():
    logging.debug('Function')
    import price_sniffer


@bot.callback_query_handler(func=lambda call: call.data == "Track")
def callback_track(call):
    if __name__ == '__main__':
        global tracker

        tracker = Process(target=track)
        tracker.start()
        time.sleep(2)

        print('\nAlive?:', tracker.is_alive())
        print(tracker.pid, '\n')
        user.tracking = True
        markup_track(call.message)


@bot.callback_query_handler(func=lambda call: call.data == "Stop")
def callback_stop(call):
    tracker.terminate()
    tracker.kill()
    bot.send_message(call.message.chat.id, "Tracking stopped")


# ----------------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    bot.polling(none_stop=True, interval=0)
