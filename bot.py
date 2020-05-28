import telebot as tlg
from KrakenInterface import KrakenInterface as KI
import time

TOKEN = ''
bot = tlg.TeleBot(TOKEN)


class User:
    def __init__(self, asset='XBT', currency='EUR'):
        self.asset = asset
        self.currency = currency
        self.state = 0
        self.cid = None
        self.uid = None
        self.help = False

user = User()
kr = KI()


# ----------------------------------------------------------------------------------------------------------------------
# Start command containing 3 buttons
@bot.message_handler(commands=['start'])
def start_message(message):
    keyboard = tlg.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.row('1 - Set asset', '2 - Set currency', '3 - List assets', '4 - Show price')
    greeting = ''
    if user.state == 0:
        greeting = f"Hi {message.chat.first_name}!\n"

    bot.send_message(message.chat.id,
                     text= greeting + f"Select one of options", reply_markup=keyboard)
# ----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# "Set asset" button containing 3 buttons
@bot.message_handler(commands=['asset'])
@bot.message_handler(func=lambda mess: '1 - Set asset' == mess.text or mess.text == '1')
def markup_asset(message):
    assets_markup = tlg.types.InlineKeyboardMarkup(row_width=2)
    XBT = tlg.types.InlineKeyboardButton("XBT", callback_data='XBT')
    ETH = tlg.types.InlineKeyboardButton("ETH", callback_data='ETH')
    ANOTHER = tlg.types.InlineKeyboardButton("Another", callback_data='Another')
    assets_markup.add(XBT, ETH, ANOTHER)
    bot.send_message(message.chat.id, "Select your asset:", reply_markup=assets_markup) # changed to message.chat.id

# "Specific asset choice"-button press handler
@bot.callback_query_handler(func=lambda call: call.data == 'XBT' or call.data == 'ETH' or call.data == 'Another')
def callback_asset(call):
    try:
        if call.data == 'XBT' or call.data == 'ETH':
            uid = call.message.chat.id
            user.asset = call.data
            user.state += 1

            bot.send_message(call.message.chat.id, "{} selected".format(user.asset))

            if user.state == 1:
                markup_currency(call.message)
            else:
                markup_current_price(call.message)

        elif call.data == 'Another':
            bot.send_message(call.message.chat.id, "Please type in asset code.\nTo see full list press /help")
            bot.register_next_step_handler(call.message, set_default_asset)

    except Exception as e:
        print(repr(e))


# Function to check if asset name is correct
def set_default_asset(message):
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
        bot.register_next_step_handler(message, set_default_asset)
# ----------------------------------------------------------------------------------------------------------------------

print('a')

# ----------------------------------------------------------------------------------------------------------------------
@bot.message_handler(func=lambda mess: mess.text == '2 - Set currency' or mess.text == '2')
def markup_currency(message):
    currency_markup = tlg.types.InlineKeyboardMarkup(row_width=2)
    USD = tlg.types.InlineKeyboardButton("USD", callback_data='USD')
    EUR = tlg.types.InlineKeyboardButton("EUR", callback_data='EUR')
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
@bot.message_handler(func=lambda mess: mess.text == '4 - Show price' or mess.text == '4')
def markup_current_price(message):
    current_price_markup = tlg.types.InlineKeyboardMarkup()
    current_price = tlg.types.InlineKeyboardButton("Show current price", callback_data='current_price')
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
@bot.message_handler(func=lambda mess: mess.text == '3 - List assets' or mess.text == '3')
@bot.message_handler(commands=['help'])
def help_message(message):
    bot.send_message(message.from_user.id, "Valid assets are: \n```\n" + KI().crypto_names + "\n```",
                     parse_mode='MarkDown')
    if user.help:
        user.help = False
        bot.register_next_step_handler(message, set_default_asset)
# ----------------------------------------------------------------------------------------------------------------------

bot.polling(none_stop=True, interval=0)
