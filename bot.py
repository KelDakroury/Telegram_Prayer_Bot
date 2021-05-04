"""
reference:
 https://medium.com/@liuhh02
"""
import os
import logging
import gspread
import sys

from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext
from dotenv import load_dotenv
from datetime import datetime, time, timedelta, timezone
from calendar import monthrange
from dbhelper import DBHelper


load_dotenv()
scopes = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scopes)
gc = gspread.authorize(creds)
worksheet = gc.open_by_url('https://docs.google.com/spreadsheets/d/1box4YoEMuMTrsZREKvo1bqObxNzQBCuOR1Lnvam8UE4/edit?usp=sharing')

prayer_names = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']

# Preparing for the database to store the  userids
db = DBHelper()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

TOKEN = os.getenv('BOT_TOKEN')

updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher
j = updater.job_queue

moscow = timezone(timedelta(hours=3))

def get_month_times():
    '''Fetches today's prayer times and returns them as a list of 5 elements.'''
    now =  datetime.now(moscow)
    sheet = worksheet.worksheet(now.strftime('%B %Y'))
    days = monthrange(now.year, now.month)[1]
    columns = ['C', 'F', 'H', 'J', 'K']
    ranges = [f'{c}4:{c}{4+days-1}' for c in columns]
    prayers = [
        [cell[0] for cell in row]
        for row in sheet.batch_get(ranges)
    ]
    return prayers


def remind_next_prayer(context: CallbackContext):
    '''Sends a message reminding about the prayer.'''
    prayer_name = context.job.context['prayer_name']
    chat_id = context.job.context['chat_id']
    context.bot.send_message(chat_id=chat_id,
                             text=f" {prayer_name}was at 23:45!")


def register_todays_prayers(context: CallbackContext):
    '''Registers callbacks for all of today's prayers.'''
    uid = context.job.context['chat_id']
    logging.info(f'Registering today\'s prayers for {uid}')
    prayer_times = get_month_times()
    today = datetime.now(moscow).day - 1
    for name, prayer_time in zip(prayer_names, prayer_times):
        prayer_time = prayer_time[today]
        timestamp = [int(x) for x in prayer_time.split(':')]
        timestamp = time(*timestamp, tzinfo=moscow)
        # Don't register past prayers
        if timestamp < datetime.now(moscow).time().replace(tzinfo=moscow):
            continue
        j.run_once(remind_next_prayer, timestamp, context={
            'chat_id': uid,
            'prayer_name': name,
        })
        logging.info(f'Registered callback for {name} for {uid} registered at {timestamp}')

def send_todays_times(update: Update, context: CallbackContext):
    times = get_month_times()
    today = datetime.now(moscow).day - 1
    prayers = [f"*{name}*: {time[today]}" for name, time in zip(prayer_names, times)]
    prayers_list = '\n'.join(prayers)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=f"Today's prayer times:\n{prayers_list}",
                             parse_mode=ParseMode.MARKDOWN_V2)

def start(update: Update, context: CallbackContext):
    new_id = update.effective_chat.id
    context.chat_data['id'] = new_id
    user = db.get_user(new_id)
    if user is not None and user.active:
        context.bot.send_message(chat_id=new_id,
                                 text="The bot is already activated.""")
        return

    db.add_user(new_id)

    job = j.run_daily(register_todays_prayers, time(0, 0, tzinfo=moscow), context={
        'chat_id': new_id,
    })
    job.run(dispatcher) # Run just once (for today)
    context.bot.send_message(chat_id=new_id,
                             text="I will send you a reminder everyday on the prayer times of that day.\n"
                                "Send /stop to stop reminding, /today to get just today's prayer times, "
                                "and /start to start again.""")

def stop(update: Update, context: CallbackContext):
    uid = update.effective_chat.id
    user = db.get_user(uid)

    # for job in j.jobs():
    #     print(job)

    context.bot.send_message(chat_id=uid,
                             text="Sorry. Not yet implemented :(")


start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

today_handler = CommandHandler('today', send_todays_times)
dispatcher.add_handler(today_handler)

stop_handler = CommandHandler('stop', stop)
dispatcher.add_handler(stop_handler)

users = db.list_users()
for user in users:
    job = j.run_daily(register_todays_prayers, time(0, 0, tzinfo=moscow), context={
        'chat_id': user.id,
    })
    job.run(dispatcher) # Run just once (for today)

if 'ON_HEROKU' in os.environ:
    # set the port number to listen in for the webhook.
    port = int(os.environ.get('PORT', 5000))
    updater.start_webhook(listen="0.0.0.0",
                            port=port,
                            url_path=TOKEN)
    updater.bot.setWebhook('https://innoprayerbot.herokuapp.com/' + TOKEN)
else:
    updater.start_polling()

updater.idle()
