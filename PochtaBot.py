import telebot
from telebot import types
from pony.orm import *
import RussianPostAPI
from RussianPostAPI import RussianPostAPI
import ShipmentInfoParser
from ShipmentInfoParser import ShipmentInfoParser
from time import sleep
import schedule
from threading import Thread
from sys import argv

_, DB_URL, DEBUG = argv
DEBUG = DEBUG == bool(DEBUG)

db = Database()
db.bind(provider='sqlite', filename=DB_URL, create_db=False)
set_sql_debug(False)


class Shipment(db.Entity):
    _table_ = "PM_SHIPMENT"
    id = PrimaryKey(int, auto=True)
    barcode = Required(str)
    chat = Required(int)
    last_event = Required(int)
    last_event_result = Required(int)


class Configuration(db.Entity):
    _table_ = "PM_SETTING"
    id = PrimaryKey(int, auto=True)
    param = Required(str)
    value = Required(str)
    description = Optional(str)


db.generate_mapping(create_tables=False)

# read configuration parameters from DB
with db_session:
    # no try block - if this fails we cant continue
    CFG_BOT_ID = Configuration[1].value
    CFG_POSTAL_API_KEY = Configuration[2].value
    CFG_POSTAL_API_PASS = Configuration[3].value
    CFG_AUTO_NOTIFICATION_INTERVAL = int(Configuration[4].value)
    CFG_MAX_BUTTONS_TO_SHOW = int(Configuration[5].value)


def get_shipment_description(shipment_info, last_event):
    # presence of last_event is reserved for future use
    return str(shipment_info)


COMMAND_START = "start"
COMMAND_LIST_READY_FOR_COLLECTION = "Ready for Collection?"
COMMAND_START_NOTIFICATION = "Start Notification"
COMMAND_STOP_NOTIFICATION = "Stop Notification"
MESSAGE_START = 'Hello, enter shipment id for info (13-14 symbols)'
MESSAGE_NOTHING_READY_FOR_COLLECTION = "No shipments to collect"
MESSAGE_ARCHIVED_SHIPMENT = "This shipment has been delivered, try again"
MESSAGE_INVALID_SHIPMENT = "Can't find this shipment id, try again"
MESSAGE_INVALID_SHIPMENT_FORMAT = "Please re-enter, shipment id must be 13-14 symbols"
MESSAGE_GENERAL_ERROR = "Error processing request, try again"
BUTTON_AUTO_NOTIFICATION_ON = "Automatic notifications are ON"
BUTTON_AUTO_NOTIFICATION_OFF = "Automatic notifications are OFF"

auto_notified_chats = set()

# Create bot
bot = telebot.TeleBot(CFG_BOT_ID)


# Start command Handler
@bot.message_handler(commands=[COMMAND_START])
def start(message, res=False):
    markup = draw_buttons(message.chat.id)
    bot.send_message(message.chat.id, MESSAGE_START, reply_markup=markup)


def draw_buttons(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    # collect my mail button
    item = types.KeyboardButton(COMMAND_LIST_READY_FOR_COLLECTION)
    markup.add(item)
    try:
        with db_session:
            # generate buttons for all non-delivered shipments we have in DB
            non_delivered_shipments = select(
                shipment for shipment in Shipment if shipment.chat == chat_id and shipment.last_event != 2
            )
            buttons_counter = 2 # two buttoms are always on the screen
            for non_delivered_shipment in non_delivered_shipments:

                # do not clutter entire screen with buttons
                if buttons_counter > CFG_MAX_BUTTONS_TO_SHOW:
                    break

                item = types.KeyboardButton(non_delivered_shipment.barcode)
                markup.add(item)
                buttons_counter += 1

    except Exception as e:
        print("Exception in draw buttons procedure", e)
        if DEBUG:
            raise e

    # show Start/Stop Automated Notification button
    item = types.KeyboardButton(
        COMMAND_STOP_NOTIFICATION if chat_id in auto_notified_chats else COMMAND_START_NOTIFICATION
    )
    markup.add(item)
    return markup


# Handle user messages
@bot.message_handler(content_types=["text"])
def handle_text(message):
    try:
        user_entry = message.text.strip()
        answer = None
        with db_session:

            if user_entry == COMMAND_LIST_READY_FOR_COLLECTION:

                # we will find shipments that are registered in DB but not marked as arrived/delivered
                shipments_to_check_for_arrival = select(
                    shipment for shipment in Shipment if shipment.chat == message.chat.id and \
                    (shipment.last_event != 2 and not (shipment.last_event == 8 and shipment.last_event_result == 2))
                )
                # and will request Russian Post for their up-to-date status and commit this updated status to DB
                for shipment_db_record in shipments_to_check_for_arrival:
                    shipment_xml = RussianPostAPI.get_shipment_data(
                        shipment_db_record.barcode, CFG_POSTAL_API_KEY, CFG_POSTAL_API_PASS
                    )
                    shipment_info = ShipmentInfoParser.parse_xml(shipment_xml)
                    shipment_db_record.last_event = shipment_info.events[-1][0]
                    shipment_db_record.last_event_result = shipment_info.events[-1][4]

                # now we have uo-to-date status of arrival in the DB
                # reading it from the DB
                arrived_shipments = select(
                    shipment for shipment in Shipment if shipment.chat == message.chat.id and shipment.last_event == 8 \
                    and shipment.last_event_result == 2
                )

                answer = ""
                for shipment_db_record in arrived_shipments:
                    answer += str(shipment_db_record.barcode) + "\n"
                if not answer:
                    answer = MESSAGE_NOTHING_READY_FOR_COLLECTION

            elif user_entry == COMMAND_START_NOTIFICATION:
                auto_notified_chats.add(message.chat.id)
                answer = BUTTON_AUTO_NOTIFICATION_ON

            elif user_entry == COMMAND_STOP_NOTIFICATION:
                if message.chat.id in auto_notified_chats:
                    auto_notified_chats.remove(message.chat.id)
                answer = BUTTON_AUTO_NOTIFICATION_OFF

            elif user_entry and 13 <= len(user_entry) <= 14:

                barcode = user_entry
                shipment_db_record = Shipment.get(barcode=barcode, chat=message.chat.id)
                if shipment_db_record:
                    # barcode was found in the DB
                    shipment_xml = RussianPostAPI.get_shipment_data(barcode, CFG_POSTAL_API_KEY, CFG_POSTAL_API_PASS)
                    shipment_info = ShipmentInfoParser.parse_xml(shipment_xml)
                    shipment_db_record.last_event = shipment_info.events[-1][0]
                    shipment_db_record.last_event_result = shipment_info.events[-1][4]

                    answer = get_shipment_description(shipment_info, 0)

                else:
                    # barcode not found in DB
                    shipment_xml = RussianPostAPI.get_shipment_data(barcode, CFG_POSTAL_API_KEY, CFG_POSTAL_API_PASS)
                    shipment_info = ShipmentInfoParser.parse_xml(shipment_xml)

                    if shipment_info and shipment_info.events[-1][0] == 2:
                        # Russian post says is has been collected - nothing to track
                        answer = MESSAGE_ARCHIVED_SHIPMENT

                    elif shipment_info:

                        # new and undelivered shipment
                        shipment_db_record = Shipment(
                            barcode=barcode,
                            chat=message.chat.id,
                            last_event=shipment_info.events[-1][0],
                            last_event_result=shipment_info.events[-1][4]
                        )
                        answer = get_shipment_description(shipment_info, 0)

                    else:
                        # Russian Post returned error or shipment not found by ID (invalid id)
                        answer = MESSAGE_INVALID_SHIPMENT

            else:
                # user entry has invalid format
                answer = MESSAGE_INVALID_SHIPMENT_FORMAT

    except Exception as e:
        print("Exception processing user entry", e)
        answer = MESSAGE_GENERAL_ERROR
        if DEBUG:
            raise e

    if not answer:
        print("Empty answer - logical failure")
        answer = MESSAGE_GENERAL_ERROR

    markup = draw_buttons(message.chat.id)
    bot.send_message(message.chat.id, answer, reply_markup=markup)


def schedule_checker():
    while True:
        schedule.run_pending()
        sleep(5)# unload CPU between schedule runs


# this procedure checks if there is update to shipment registered in DB
def automated_notification_procedure():
    try:
        with db_session:
            for chat_id in auto_notified_chats:
                non_delivered_shipments = select(
                    shipment for shipment in Shipment if shipment.chat == chat_id and shipment.last_event != 2
                )

                for non_delivered_shipment in non_delivered_shipments:

                    shipment_xml = RussianPostAPI.get_shipment_data(
                        non_delivered_shipment.barcode, CFG_POSTAL_API_KEY, CFG_POSTAL_API_PASS
                    )
                    shipment_info = ShipmentInfoParser.parse_xml(shipment_xml)

                    if shipment_info.events[-1][0] != non_delivered_shipment.last_event or \
                            shipment_info.events[-1][4] != non_delivered_shipment.last_event_result:
                        answer = get_shipment_description(shipment_info, 0)
                        non_delivered_shipments.last_event = shipment_info.events[-1][0]
                        non_delivered_shipments.last_event_result = shipment_info.events[-1][4]

                        # as a result of above code some items may becime "delivered",
                        # so we need to hide them so we have to redraw buttons
                        markup = draw_buttons(chat_id.chat.id)

                        bot.send_message(chat_id, answer, markup)

    except Exception as e:
        print("Exception in Auto Notification Procedure", e)
        if DEBUG:
            raise e


# Create the job with schedule
schedule.every(CFG_AUTO_NOTIFICATION_INTERVAL).minutes.do(automated_notification_procedure)

# Spin up a thread to run the schedule check so it doesn't block the bot.
# Teacher please understand and forgive there is no thread safety implemented.
Thread(target=schedule_checker).start()

while True:
    print("The bot is now running")
    try:
        bot.polling(none_stop=True, interval=0)

    except Exception as e:
        print("Message polling has restarted with the following reason:", e)
        if DEBUG:
            raise e
