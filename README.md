# Saba Pharma Bot

A streamlined Telegram bot that quickly fetches UK pharmacy data from PharmData.co.uk. This bot accepts UK postcodes or direct pharmacy ODS codes and returns detailed information about pharmacies including their services and metrics.

📱 [Open in Telegram: @saba_pharma_bot](https://t.me/saba_pharma_bot)

## Key Features

- 🔍 **Pharmacy Search**: Find pharmacies near any UK postcode
- 🏥 **Direct Lookup**: Look up pharmacies by their ODS codes (e.g., FJ144)
- 💊 **Service Overview**: See what services are available at the pharmacy with metrics
- 📋 **Clean Interface**: Each pharmacy displayed in a separate message for easy reading
- 🔗 **Direct Links**: Links to view full pharmacy details on PharmData
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
2. **Wait for Results**: The bot searches pharmdata.co.uk for nearby pharmacies
3. **View Pharmacy Services**: Receive information about multiple pharmacies with their services and metrics
4. **Direct Lookup**: Alternatively, enter an ODS code (like FJ144) to look up a specific pharmacy

### Sample Output

```
📊 Pharmacy Information 📊

🏥 Pharmacy: Boots
📮 Postcode: W9 1SY
🔗 More info: https://www.pharmdata.co.uk/nacs_select.php?query=FJ144

📦 Items Dispensed: 15,234
📝 Prescriptions: 4,210
🩺 CPCS: 122
💊 Pharmacy First: 76
🔄 NMS: 89
💻 EPS Takeup: 85%
```

## Important Notes

This bot now uses a **worker** dyno with **polling mode** instead of webhook mode. This approach is more reliable on Heroku, as it doesn't require handling webhook callbacks and avoids complications with HTTPS and event loops.

## Performance Optimizations

This bot has been specially optimized for performance on Heroku:

1. **Boots Priority**: Shows Boots pharmacies first, followed by other pharmacies
2. **ODS Code Lookup**: Direct lookup of pharmacies by their ODS code
3. **Detailed Output**: Clean display of services with numeric values
4. **Chrome Optimizations**: Minimizes memory and CPU usage for headless Chrome
5. **Timeout Protection**: Gracefully handles timeouts and prevents hanging
6. **UK Postcode Validation**: Flexible validation accepting multiple formats
7. **Error Recovery**: Continues with available data even when timeouts occur

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
