# Saba Pharma Bot

A streamlined Telegram bot that quickly fetches UK pharmacy data, specializing in Boots pharmacies. This bot accepts UK postcodes or direct pharmacy ODS codes and returns information about Boots pharmacies including their services.

📱 [Open in Telegram: @saba_pharma_bot](https://t.me/saba_pharma_bot)

## Key Features

- 🔍 **Boots Pharmacy Search**: Find Boots pharmacies near any UK postcode
- 🏥 **Direct Lookup**: Look up pharmacies by their ODS codes (e.g., FJ144)
- 💊 **Service Overview**: See what services are available at the pharmacy
- 📋 **Clean Interface**: Simple and easy-to-read results
- 🚀 **Parallel Processing**: Uses concurrent tasks for faster results
- ⏱️ **Timeout Protection**: Optimized for reliable performance on Heroku

## Requirements

- Python 3.9+
- Telegram Bot Token
- Chrome browser (provided by buildpacks in Heroku)

## Deployment on Heroku

### Quick Deployment

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/YOUR_GITHUB_USERNAME/saba-pharma-bot)

### Manual Deployment

1. Create a new Heroku app:
```bash
heroku create saba-pharma-bot
```

2. Add the necessary buildpacks (in this order):
```bash
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-chrome-for-testing.git --app saba-pharma-bot
heroku buildpacks:add --index 2 https://github.com/heroku/heroku-buildpack-apt.git --app saba-pharma-bot
heroku buildpacks:add --index 3 heroku/python --app saba-pharma-bot
```

3. Set the required environment variables:
```bash
heroku config:set TELEGRAM_BOT_TOKEN=your_telegram_bot_token --app saba-pharma-bot
```

4. Deploy the app:
```bash
git push heroku main
```

5. Scale the worker dyno:
```bash
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
2. **Wait for Results**: The bot searches pharmdata.co.uk for Boots pharmacies
3. **View Pharmacy Services**: Receive information about the Boots pharmacy
4. **Direct Lookup**: Alternatively, enter an ODS code (like FJ144) to look up a specific pharmacy

### Sample Output

```
📊 Pharmacy Information 📊

🏥 Pharmacy: Boots
📮 Postcode: W9 1SY

📦 Items Dispensed
📝 Prescriptions
🩺 CPCS
💊 Pharmacy First
🔄 NMS
💻 EPS Takeup
```

## Important Notes

This bot now uses a **worker** dyno with **polling mode** instead of webhook mode. This approach is more reliable on Heroku, as it doesn't require handling webhook callbacks and avoids complications with HTTPS and event loops.

## Performance Optimizations

This bot has been specially optimized for performance:

1. **Concurrent Processing**: Uses asyncio to process pharmacy data in parallel
2. **Efficient Waiting**: Uses WebDriverWait instead of sleep() for faster page loading
3. **Timeouts**: Implements proper timeouts to prevent hanging operations
4. **Smart Limiting**: Only processes the top 3 pharmacy results for speed
5. **UK Postcode Validation**: Validates postcode format before processing
6. **Error Recovery**: Gracefully handles timeouts and continues with partial results

## Troubleshooting

If you encounter any issues:

1. Check the logs: `heroku logs --tail --app saba-pharma-bot`
2. Ensure the worker is running: `heroku ps --app saba-pharma-bot`
3. Restart the worker if needed: `heroku ps:restart worker --app saba-pharma-bot`
4. Make sure all buildpacks are properly installed: `heroku buildpacks --app saba-pharma-bot`

### Common Issues

1. **Bot not responding**: Make sure the worker dyno is running with `heroku ps`
2. **Chrome errors**: Check that all Chrome dependencies are in Aptfile
3. **Rate limiting**: If you see 429 errors, your bot may be hitting Telegram's rate limits
4. **Slow responses**: The bot has timeouts to prevent hanging - if searches take too long, try again later

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) library for Telegram Bot API
- [Selenium](https://selenium-python.readthedocs.io/) for web scraping
- [Heroku](https://heroku.com) for hosting
- [PharmData](https://pharmdata.co.uk) for pharmacy information
