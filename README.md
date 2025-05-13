# Saba Pharma Bot

A Telegram bot that fetches UK pharmacy data using web scraping techniques. This bot accepts UK postcodes and returns information about nearby pharmacies including items dispensed, prescriptions, CPCS, Pharmacy First, NMS, and EPS takeup data.

## UPDATE: New Simple Implementation

The bot has been reimplemented in a single `bot.py` file with a more reliable structure for Heroku deployment. This new implementation follows best practices and handles webhooks correctly.

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

Note: The `APP_NAME` must match your Heroku app name exactly for webhooks to work properly.

4. Deploy the app:
```
git push heroku main
```

5. Ensure the web dyno is running:
```
heroku ps:scale web=1 --app saba-pharma-bot
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
python bot.py
```

## Features

- Searches for UK pharmacies by postcode
- Retrieves detailed pharmacy data from PharmData.co.uk
- Presents information in an easy-to-read format
- Works with Telegram's messaging interface
- Handles errors gracefully with retries

## Project Structure

- `bot.py` - Complete bot implementation in a single file (new simplified version)
- `pharmacy_data.py` - Original bot code (deprecated)
- `Procfile` - Heroku process definition file (uses web dyno for webhook)
- `requirements.txt` - Python dependencies
- `Aptfile` - System dependencies for Chrome and X11 libraries
- `runtime.txt` - Python runtime version
- `.gitignore` - Files and directories to exclude from git

## Web vs Worker Dynos

This bot uses a **web** dyno instead of a worker dyno because:

1. **Webhook Mode** - When a Telegram bot uses webhook mode, it needs to receive HTTP requests from Telegram's servers. Only web dynos can receive incoming HTTP requests in Heroku.

2. **Port Binding** - Web dynos bind to a port (provided by Heroku as the PORT environment variable) and can accept incoming connections, which is essential for webhooks.

3. **Always On** - Both web and worker dynos can run continuously, but only web dynos can respond to HTTP requests from external services.

If you were to use polling mode instead of webhook mode, you would use a worker dyno because polling doesn't require accepting incoming HTTP connections.

## Troubleshooting

### Event Loop Errors

If you encounter errors like "Cannot close a running event loop", the bot architecture handles this by:

1. Separating the bot logic (`pharmacy_data.py`) from the entry point (`run.py`)
2. Using `close_loop=False` in the webhook and polling configurations
3. Using `asyncio.run()` instead of manually managing event loops

### Chrome/Selenium Issues

If you encounter Chrome or Selenium-related errors:

1. Check if all required X11 libraries are in the `Aptfile`
2. Verify that the Chrome binary is being found correctly in the logs
3. Try switching to a different Chrome version or ChromeDriver

### Webhook Issues

If the webhook isn't receiving messages:

1. Confirm that `APP_NAME` is set correctly and matches your Heroku app name exactly
2. Check the logs for successful webhook registration
3. Make sure `python-telegram-bot[webhooks]` is installed correctly
4. Use the included `test_webhook.py` script to diagnose webhook issues:
   ```
   python test_webhook.py
   ```
5. Ensure your Heroku app is properly scaled with `heroku ps:scale web=1`
6. Check if you're hitting Telegram's rate limits (errors like "429 Too Many Requests")
7. Test the bot in polling mode locally to confirm basic functionality

Note: The Python Telegram Bot library requires the optional webhooks dependency to be installed. This is included in the requirements.txt file as `python-telegram-bot[webhooks]`.
