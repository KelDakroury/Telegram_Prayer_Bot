"""
Simple Bot to reply to Telegram messages taken from the python-telegram-bot examples.
Deployed using heroku.
Author: liuhh02 https://medium.com/@liuhh02
"""
import os
import logging
import gspread
import sys


from oauth2client.service_account import ServiceAccountCredentials
from telegram.ext import Updater, CommandHandler
from dotenv import load_dotenv
from datetime import datetime, time, date, timedelta, timezone
from calendar import monthrange
from dbhelper import DBHelper

load_dotenv()
# parsing data first!!, into a 2D array
scope = [
    "https://spreadsheets.google.com/feeds",
    'https://www.googleapis.com/auth/spreadsheets',
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
gc = gspread.authorize(creds)
worksheet = gc.open_by_url('https://docs.google.com/spreadsheets/d/1ozuBggiT-rBfnzP3zr6ubLOE2TtI1gY6nNtBUWbYLcE/edit#gid=1478484939')

prayer_names = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']

#preparing for the database to store the  userids
db = DBHelper()

#set the port number to listen in for the webhook.
PORT = int(os.environ.get('PORT', 5000))

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

TOKEN = os.getenv('BOT_TOKEN')
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher
j = updater.job_queue
moscow = timezone(timedelta(hours=3))

def get_month_times():
    now = date.today()
    sheet = worksheet.worksheet(date.strftime(now, '%B %Y'))
    days = monthrange(now.year, now.month)[1]
    columns = ['C', 'F', 'H', 'J', 'K']
    ranges = [f'{c}4:{ c}{4+days-1}' for c in columns]
    fajr, dohr, asr, maghrib, isha = [
        [cell[0] for cell in row]
        for row in sheet.batch_get(ranges)
    ]
    return fajr, dohr, asr, maghrib, isha


def remind_next_prayer(context):
    prayer_name = context.job.context['prayer_name']
    chat_id = context.job.context['uid']
    context.bot.send_message(chat_id=chat_id,
                             text=f"{prayer_name} prayer is NOW!")


def register_todays_prayers(context):
    logging.info('Registering today\'s prayers')
    prayer_times = get_month_times()
    """for job in j.jobs:
        job.schedule_removal()"""
    for prayer in range(5):
        prayer_time = prayer_times[prayer][datetime.now().day - 1]
        timestamp = [int(x) for x in prayer_time.split(':')]
        timestamp = time(*timestamp, tzinfo=moscow)
        logging.info(f'Registered callback for {prayer_names[prayer]} registered at {timestamp}')
        j.run_once(remind_next_prayer, timestamp, context={
            'uid': context.job.context['uid'], 
            'prayer_name': prayer_names[prayer],
        })

def start(update, context):
    new_id = update.effective_chat.id
    db.add_id(new_id)
    context.bot.send_message(chat_id=new_id,
                             text="Prayer Times bot start")
    # now = datetime.now()
    j.run_once(register_todays_prayers, 5, context={'uid': new_id})
    j.run_daily(register_todays_prayers, time(hour=0), context={'uid': new_id})


start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

if 'ON_HEROKU' in os.environ:
    updater.start_webhook(listen="0.0.0.0",
                            port=PORT,
                            url_path=TOKEN)
    updater.bot.setWebhook('https://stark-stream-60602.herokuapp.com/' + TOKEN)
else:
    updater.start_polling()

updater.idle()


