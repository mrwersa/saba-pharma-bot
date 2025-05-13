# Saba Pharma Bot

A Telegram bot that fetches UK pharmacy data using web scraping techniques. This bot accepts UK postcodes and returns information about nearby pharmacies including items dispensed, prescriptions, CPCS, Pharmacy First, NMS, and EPS takeup data.

📱 [Open in Telegram: @saba_pharma_bot](https://t.me/saba_pharma_bot)

## Key Features

- 🔍 **Instant Pharmacy Search**: Find pharmacies near any UK postcode
- 📊 **Comprehensive Data**: Get detailed dispensing and service information
- 📈 **3-Month Averages**: View recent performance metrics
- 💊 **Multiple Services**: CPCS, Pharmacy First, NMS, and EPS statistics
- 🚀 **Fast Results**: Multiple pharmacy results in seconds

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
python pharmacy_bot.py
```

## How It Works

1. **Enter a UK Postcode**: Send any valid UK postcode to the bot
2. **Wait for Results**: The bot searches pharmdata.co.uk for matching pharmacies
3. **View Pharmacy Data**: Receive detailed information about nearby pharmacies
4. **Compare Statistics**: See dispensing figures and service provision data

### Sample Output

```
📊 Results (3-Month Averages) 📊

🏥 Pharmacy: Boots (E1 6AN)
📦 Items Dispensed: 12,456
📝 Prescriptions: 4,789
🩺 CPCS: 321
💊 Pharmacy First: 156
🔄 NMS: 89
💻 EPS Takeup: 93%

🏥 Pharmacy: Lloyds Pharmacy (E1 7RT)
📦 Items Dispensed: 9,872
📝 Prescriptions: 3,456
🩺 CPCS: 213
💊 Pharmacy First: 118
🔄 NMS: 67
💻 EPS Takeup: 87%
```

## Important Notes

This bot now uses a **worker** dyno with **polling mode** instead of webhook mode. This approach is more reliable on Heroku, as it doesn't require handling webhook callbacks and avoids complications with HTTPS and event loops.

## Troubleshooting

If you encounter any issues:

1. Check the logs: `heroku logs --app saba-pharma-bot`
2. Ensure the worker is running: `heroku ps --app saba-pharma-bot`
3. Restart the worker if needed: `heroku ps:restart worker --app saba-pharma-bot`
4. Make sure all buildpacks are properly installed: `heroku buildpacks --app saba-pharma-bot`
