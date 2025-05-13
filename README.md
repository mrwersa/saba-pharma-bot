# Saba Pharma Bot

A Telegram bot that fetches UK pharmacy data using web scraping techniques. This bot accepts UK postcodes and returns information about nearby pharmacies including items dispensed, prescriptions, CPCS, Pharmacy First, NMS, and EPS takeup data.

## Requirements

- Python 3.9+
- Telegram Bot Token
- Chrome browser (provided by buildpacks in Heroku)

## Deployment on Heroku

1. Create a new Heroku app:
```
heroku create saba-pharma-bot
```

2. Add the necessary buildpacks (in this order):
```
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-chrome-for-testing.git --app saba-pharma-bot
heroku buildpacks:add --index 2 https://github.com/heroku/heroku-buildpack-apt.git --app saba-pharma-bot
heroku buildpacks:add --index 3 heroku/python --app saba-pharma-bot
```

3. Set the required environment variables:
```
heroku config:set TELEGRAM_BOT_TOKEN=your_telegram_bot_token --app saba-pharma-bot
heroku config:set APP_NAME=saba-pharma-bot --app saba-pharma-bot
```

4. Deploy the app:
```
git push heroku main
```

5. Scale the worker dyno:
```
heroku ps:scale worker=1 --app saba-pharma-bot
```

## Local Development

1. Create a `.env` file with the following variables:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

2. Install dependencies:
```
pip install -r requirements.txt
```

3. Run the bot:
```
python pharmacy_data.py
```

## Features

- Searches for UK pharmacies by postcode
- Retrieves detailed pharmacy data from PharmData.co.uk
- Presents information in an easy-to-read format
- Works with Telegram's messaging interface
- Handles errors gracefully with retries

## Project Structure

- `pharmacy_data.py` - Main bot code with scraping functions
- `Procfile` - Heroku process definition file
- `requirements.txt` - Python dependencies
- `Aptfile` - System dependencies for Chrome
- `runtime.txt` - Python runtime version
