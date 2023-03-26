"""
reference:
 https://medium.com/@liuhh02
"""
import os
import logging
from datetime import datetime, time, timedelta, timezone
from calendar import monthrange
import gspread

from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackContext, ApplicationBuilder
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import numpy as np
from humanize import precisedelta

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

prayer_names = ['Fajr', 'Sunrise' , 'Dhuhr', 'Asr', 'Maghrib', 'Isha']

# Preparing for the database to store the  userids
db = DBHelper()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

TOKEN = os.getenv('BOT_TOKEN')

bot = ApplicationBuilder().token(TOKEN).build()
j = bot.job_queue

moscow = timezone(timedelta(hours=3))

now = datetime.now(moscow)
sheet = worksheet.worksheet(now.strftime('%B %Y'))
days = monthrange(now.year, now.month)[1]
columns = ['C', 'E' ,'F', 'H', 'J', 'L']
ranges = [f'{c}4:{c}{4+days-1}' for c in columns]
prayers = [
    [cell[0] for cell in row]
    for row in sheet.batch_get(ranges)
]
last_updated_at = now

def get_month_times():
    '''Fetches today's prayer times and returns them as a list of 5 elements.'''
    global last_updated_at, prayers
    now = datetime.now(moscow)
    if now.month != last_updated_at.month:
        sheet = worksheet.worksheet(now.strftime('%B %Y'))
        days = monthrange(now.year, now.month)[1]
        ranges = [f'{c}4:{c}{4+days-1}' for c in columns]
        prayers = [
            [cell[0] for cell in row]
            for row in sheet.batch_get(ranges)
        ]
        last_updated_at = now
    return prayers



async def remind_next_prayer(context: CallbackContext):
    """Sends a message reminding about the prayer."""
    prayer_name = context.job.context['prayer_name']
    chat_id = context.job.context['chat_id']
    user = db.get_user(chat_id)
    if not user.active:
        return
    try:
        await context.bot.send_message(chat_id=chat_id,
                                text=f"It's time for {prayer_name}!")
    except:
        pass

def register_todays_prayers(context: CallbackContext):
    """Registers callbacks for all of today's prayers."""
    uid = context.job.context['chat_id']
    user = db.get_user(uid)
    if not user.active:
        return
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
        j.run_once(remind_next_prayer, timestamp, data={
            'chat_id': uid,
            'prayer_name': name,
        })

        logging.info(f'Registered callback for {name} for {uid} registered at {timestamp}')

async def send_todays_times(update: Update, context: CallbackContext):
    times = get_month_times()
    today = datetime.now(moscow).day - 1
    prayers = [f"*{name}*: {time[today]}" for name, time in zip(prayer_names, times)]
    prayers_list = '\n'.join(prayers)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                             text=f"Today's prayer times:\n{prayers_list}",
                             parse_mode=ParseMode.MARKDOWN_V2)

async def send_tomorrows_times(update: Update, context: CallbackContext):
    times = get_month_times()
    now = datetime.now(moscow)
    _, days_in_month = monthrange(now.year, now.month)
    tomorrow = now.day
    if tomorrow >= days_in_month:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                text="Sorry, this feature doesn't work"
                                     " on the last day of the month yet :(",
                                parse_mode=ParseMode.MARKDOWN_V2)
        return
    prayers = [f"*{name}*: {time[tomorrow]}" for name, time in zip(prayer_names, times)]
    prayers_list = '\n'.join(prayers)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                             text=f"Tomorrow's prayer times:\n{prayers_list}",
                             parse_mode=ParseMode.MARKDOWN_V2)

async def send_next_prayer(update: Update, context: CallbackContext):
    times = get_month_times()
    now = datetime.now(moscow)
    today = now.day
    with_time = lambda p_time, day=today: now.replace(day=day, hour=int(p_time.split(':')[0]), minute=int(p_time.split(':')[1]))
    prayer_times = [with_time(time[today - 1]) for time in times]
    _, days_in_month = monthrange(now.year, now.month)
    tomorrow = now.day + 1
    if tomorrow < days_in_month + 1:
        prayer_times += [with_time(time[tomorrow - 1], tomorrow) for time in times]

    requested_prayer = None
    command = update.effective_message.text.split(' ', 1)
    if len(command) == 2:
        requested_prayer = command[1]
        if requested_prayer not in prayer_names:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                    text="Unkown value for prayer time\n"
                                        f"Available values are: {', '.join(prayer_names)}",
                                    parse_mode=ParseMode.MARKDOWN_V2)
            return

    prayer_time = None
    if requested_prayer is None:
        prayer_time = next((p_time for p_time in prayer_times if p_time > now), None)
        if prayer_time is not None:
            requested_prayer = prayer_names[prayer_times.index(prayer_time) % len(prayer_names)]
    else:
        prayer_idx = prayer_names.index(requested_prayer)
        if prayer_idx + 1 < len(prayer_times):
            prayer_time = prayer_times[prayer_idx + 1]

    if prayer_time is None:
        requested_prayer = 'prayer' if requested_prayer is None else requested_prayer
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                text=f"Sorry, cannot find the next {requested_prayer} time\n"
                                      "Cannot cross the month boundary \\(yet\\)\\. Please try again after 12:00 midnight",
                                parse_mode=ParseMode.MARKDOWN_V2)
        return
    await context.bot.send_message(chat_id=update.effective_chat.id,
                            text=f"The next {requested_prayer} is in {precisedelta(prayer_time - now)}"
                                 f" \\(at {prayer_time.strftime('%H:%M')}\\)",
                            parse_mode=ParseMode.MARKDOWN_V2)

async def start(update: Update, context: CallbackContext):
    new_id = update.effective_chat.id
    context.chat_data['id'] = new_id
    user = db.get_user(new_id)
    if user is None:
        user = db.add_user(new_id)
    elif user.active:
        await context.bot.send_message(chat_id=new_id,
                                 text="The bot is already activated.""")
        return
    elif not user.active:
        db.set_active(new_id, True)

    job = j.run_daily(register_todays_prayers, time(0, 0, tzinfo=moscow), data={
        'chat_id': new_id,
    })
    await job.run(bot) # Run just once (for today)
    await context.bot.send_message(chat_id=new_id,
                             text="I will send you a reminder everyday on the prayer times of that day.\n"
                                "Send /stop to stop reminding or /today to get just today's prayer times.")

async def broadcast(update: Update, context: CallbackContext):
    if update.effective_chat.id == 782144399:
        users = db.list_users()
        for user in users:
            # logging.info(f"Sending {' '.join(context.args)} to user {user.id}")
            try:
                await context.bot.send_message(chat_id=user.id, text=' '.join(context.args))
            except:
                continue

async def stop(update: Update, context: CallbackContext):
    uid = update.effective_chat.id
    db.set_active(uid, False)

    await context.bot.send_message(chat_id=uid,
                             text="Reminders stopped. To reactivate, send /start again.")


start_handler = CommandHandler('start', start)
bot.add_handler(start_handler)

today_handler = CommandHandler('today', send_todays_times)
bot.add_handler(today_handler)

tomorrow_handler = CommandHandler('tomorrow', send_tomorrows_times)
bot.add_handler(tomorrow_handler)

next_handler = CommandHandler('next', send_next_prayer)
bot.add_handler(next_handler)

stop_handler = CommandHandler('stop', stop)
bot.add_handler(stop_handler)

broadcast_handler = CommandHandler('broadcast', broadcast)
bot.add_handler(broadcast_handler)

users = db.list_users()
for user in users:
    job = j.run_daily(register_todays_prayers, time(0, 0, tzinfo=moscow), data={
        'chat_id': user.id,
    })
    job.run(bot) # Run just once (for today)

if 'ON_HEROKU' in os.environ:
    # set the port number to listen in for the webhook.
    print('Running webhook...')
    port = int(os.environ.get('PORT', 5000))
    bot.run_webhook(listen="0.0.0.0",
                            port=port,
                            url_path=TOKEN,)
    # bot.set_webhook('https://innoprayerbot.herokuapp.com/' + TOKEN)
else:
    print('Running in polling mode')
    bot.run_polling()
