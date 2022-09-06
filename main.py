import glob
import logging
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from dotenv import load_dotenv
from humanize import precisedelta
from openpyxl import load_workbook
from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.types import Message

import dbhelper

load_dotenv('.env')

app = Client(
    "InnoPrayerBot",
    api_id=os.environ["API_ID"],
    api_hash=os.environ["API_HASH"],
    bot_token=os.environ["API_TOKEN"]
)


# Initializes and returns the application logger
def init_logger():
    tmp = logging.getLogger(__name__)
    tmp.setLevel(logging.INFO)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(
        logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    )
    tmp.addHandler(sh)
    return tmp


# Adds a new user to the database
@app.on_message(filters.command('start') & filters.private)
async def start_handler(client: Client, message: Message):
    uid = message.from_user.id
    db.add_user(str(uid))
    await client.send_message(uid, 'Subscribed. You will receive reminders from the bot')


# Deletes user from the database
@app.on_message(filters.command('stop') & filters.private)
async def stop_handler(client: Client, message: Message):
    uid = message.from_user.id
    db.delete_user(str(uid))
    await client.send_message(uid, 'Unsubscribed. You will no longer receive reminders from the bot')


# Notifies user about the time remaining before the next event
async def get_next_event(start):
    for event in times.keys():
        job = scheduler.get_job(f'{start.day}.{start.month}.{start.year}:{event}')
        if job:
            remaining = precisedelta(datetime.now(tz=tz) - job.next_run_time, suppress=["seconds"], format="%0.0f")
            return f'The next {event} is in {remaining} (at {job.next_run_time.strftime("%H:%M")})'
    return None


# Notifies user about the upcoming event
@app.on_message(filters.command('next') & filters.private)
async def next_handler(client: Client, message: Message):
    now = datetime.now(tz=tz)
    uid = message.from_user.id
    message = None
    while not message:
        message = await get_next_event(now)
        now += timedelta(days=1)
    await client.send_message(uid, message)


# Gets timetable for the current month
@app.on_message(filters.command('month') & filters.private)
async def month_handler(client: Client, message: Message):
    now = datetime.now(tz=tz)
    await client.send_document(
        chat_id=message.from_user.id,
        document=f'data/{now.year}/{now.month:02}.pdf',
        file_name=f'{now.strftime("%B")}.pdf',
        caption=f'Schedule for {now.strftime("%B")} {now.strftime("%Y")}',
    )


# Sends message to all users in the database
async def notify_users(message):
    logger.info(f"Sending '{message}' to all users")
    for uid in db.list_users():
        try:
            await app.send_message(uid, message)
        except RPCError:
            logger.warning(f"Failed to notify {uid}")


# Broadcast command handler
@app.on_message(filters.command('broadcast') & filters.private)
async def broadcast_handler(client: Client, message: Message):
    uid = message.from_user.id
    if uid == int(os.environ["ADMIN_UID"]):
        await notify_users(" ".join(message.command[1:]))
    else:
        await app.send_message(uid, "You are not authorized!")


# Registers notification jobs for all events
def register_jobs():
    for k in times.keys():
        for v in times[k]:
            if v > datetime.now(tz=tz):
                scheduler.add_job(
                    id=f'{v.day}.{v.month}.{v.year}:{k}',
                    func=notify_users,
                    trigger=DateTrigger(v),
                    args=[f"It's time for {k}!"],
                    misfire_grace_time=60
                )
        logger.info(f"Registered all jobs for {k}")


# Returns the number of the first empty row in the sheet
def row_count(sheet):
    rows = 0
    for max_row, row in enumerate(sheet, 1):
        if not all(col.value is None for col in row):
            rows += 1
    return rows


# Loads all workbooks in ./data/{year}
def load_sheets(year):
    for month_file_path in glob.glob(f'data/{year}/*.xlsx'):
        logger.info(f'Loading workbook: {month_file_path}')
        sheet = load_workbook(month_file_path).active
        month = int(os.path.basename(month_file_path).split('.')[0])
        for col in range(ord('A'), ord('F') + 1):
            tmp = []
            for row in range(2, row_count(sheet) + 1):
                time = sheet[f'{chr(col)}{row}'].value
                tmp.append(datetime(year, month, row - 1, time.hour, time.minute, time.second, tzinfo=tz))
            event = sheet[f'{chr(col)}1'].value
            times[event] = times[event] + tmp if times.get(event) else tmp


if __name__ == '__main__':
    logger = init_logger()

    logger.info('Initializing')
    times = {}  # times["event_name"] = list of datetime objects
    scheduler = AsyncIOScheduler()
    tz = ZoneInfo('Europe/Moscow')

    logger.info('Connecting to Database')
    db = dbhelper.DBHelper()

    logger.info('Loading data')
    load_sheets(datetime.now(tz=tz).year)

    logger.info('Registering Jobs')
    register_jobs()

    logger.info('Starting scheduler')
    scheduler.start()

    logger.info('Starting bot')
    app.run()
