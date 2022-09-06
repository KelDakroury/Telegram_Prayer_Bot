# Telegram_Prayer_Bot

## Data directory

Files that should be in `/data` directory

- `YYYY/MM.xlsx`
    - First row should contain prayer names
    - Rest of the rows should contain prayer times for the month
- `YYYY/MM.pdf`: PDF schedules for convenience.

## Development

- The following environment variables should be set

```text
# .env.sample
API_ID=
API_HASH=
API_TOKEN=
DATABASE_URL=
ADMIN_UID=
```

```bash
git clone https://github.com/KelDakroury/Telegram_Prayer_Bot
python -m venv venv
sourve venv/bin/activate
mv .env.sample .env
python main.py
```

## Production

```bash
heroku login
heroku git:remote -a $APP_NAME
git push heroku main
heroku ps:scale worker=1 -a $APP_NAME
```
