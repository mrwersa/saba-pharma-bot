from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import asyncio
import nest_asyncio
import os
import re
import sys
import time
import logging
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Apply nest_asyncio to allow nesting of asynchronous calls
nest_asyncio.apply()

# List of User-Agents to randomize
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15A372 Safari/604.1"
]

def get_custom_chrome_options():
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")

    # Get Chrome binary from env var, with fallback path for Heroku
    chrome_bin = os.environ.get('GOOGLE_CHROME_BIN', '/app/.apt/usr/bin/google-chrome')
    if os.path.exists(chrome_bin):
        chrome_options.binary_location = chrome_bin
        logging.info(f"Using Chrome binary at: {chrome_bin}")
    else:
        logging.warning(f"Chrome binary not found at {chrome_bin}")

    return chrome_options

def clear_browser_storage(driver):
    try:
        driver.execute_script("window.localStorage.clear();")
        driver.execute_script("window.sessionStorage.clear();")
        driver.execute_script(
            "indexedDB.databases().then((dbs) => {dbs.forEach(db => indexedDB.deleteDatabase(db.name));});"
        )
        driver.execute_script(
            "caches.keys().then(function(names) { for (let name of names) caches.delete(name); });"
        )
    except Exception as e:
        print(f"Failed to clear browser storage: {e}")

def fetch_pharmacies_selenium(postcode):
    if not postcode or not isinstance(postcode, str):
        logging.error("Invalid postcode input.")
        return None

    chrome_options = get_custom_chrome_options()

    try:
        # On Heroku with buildpacks, we can initialize Chrome directly without specifying driver path
        driver = webdriver.Chrome(options=chrome_options)
        logging.info("Chrome WebDriver initialized successfully")
    except WebDriverException as e:
        logging.error(f"WebDriver failed to start: {e}")
        return None

    try:
        search_url = "https://www.pharmdata.co.uk"
        driver.get(search_url)
        clear_browser_storage(driver)

        search_box = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, 'query'))
        )
        search_box.clear()
        search_box.send_keys(postcode)
        search_box.send_keys(Keys.RETURN)

        search_results = WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'tr.search-result'))
        )

        pharmacy_ids = [
            result.get_attribute('id') for result in search_results[:5] if result.get_attribute('id')
        ]

        return pharmacy_ids if pharmacy_ids else None

    except TimeoutException:
        logging.error("Timeout while loading search results.")
        return None
    except Exception as e:
        logging.error(f"Unexpected error during pharmacy search: {e}")
        return None
    finally:
        try:
            driver.quit()
        except:
            pass

def scrape_items_and_forms_selenium(pharmacy_id):
    if not pharmacy_id:
        logging.error("No pharmacy ID provided.")
        return None

    chrome_options = get_custom_chrome_options()

    try:
        # On Heroku with buildpacks, we can initialize Chrome directly without specifying driver path
        driver = webdriver.Chrome(options=chrome_options)
        logging.info(f"Chrome WebDriver initialized successfully for pharmacy ID: {pharmacy_id}")
    except WebDriverException as e:
        logging.error(f"WebDriver failed to start: {e}")
        return None

    try:
        url = f"https://www.pharmdata.co.uk/nacs_select.php?query={pharmacy_id}"
        driver.get(url)
        clear_browser_storage(driver)

        elements = WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.list-group-item-text'))
        )

        if len(elements) < 6:
            raise ValueError("Insufficient data fields found in page.")

        items_value = elements[0].text.split()[0]
        forms_value = elements[1].text.split()[0]
        cpcs_value = elements[2].text.split()[0]
        pharmacy_first_value = elements[3].text.split()[0]
        nms_value = elements[4].text.split()[0]
        eps_text = elements[5].text
        eps_takeup_percentage = eps_text.split('%')[0].strip() + '%'

        name_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.panel-title-custom'))
        )
        pharmacy_name = name_element.text.split('(')[0].strip()

        address_text = driver.find_element(By.XPATH, "//div[contains(@class, 'col-md-3')]").text
        postcode_match = re.search(r'\b[A-Z]{1,2}\d[A-Z]?\s*\d[A-Z]{2}\b', address_text)
        postcode = postcode_match.group(0) if postcode_match else "N/A"

        return {
            'Items': items_value,
            'Forms': forms_value,
            'CPCS': cpcs_value,
            'Pharmacy First': pharmacy_first_value,
            'NMS': nms_value,
            'EPS Takeup': {'Percentage': eps_takeup_percentage},
            'Pharmacy Name': pharmacy_name,
            'Pharmacy Postcode': postcode
        }

    except TimeoutException:
        logging.error(f"Timed out while loading pharmacy details for ID: {pharmacy_id}")
        return None
    except Exception as e:
        logging.error(f"Error while scraping data for pharmacy ID {pharmacy_id}: {e}")
        return None
    finally:
        try:
            driver.quit()
        except:
            pass

# Telegram bot command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logging.info(f"Received /start command from user {update.effective_user.id}")
        await update.message.reply_text('سلام عزیزم! من ربات اطلاعات داروخانه هستم. لطفاً یک کد پستی بریتانیا وارد کن')
    except Exception as e:
        logging.error(f"Error in start command: {e}")

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logging.info(f"Received message from user {update.effective_user.id}: {update.message.text[:15]}...")
        postcode = update.message.text.strip()
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        return

    if not postcode:
        await update.message.reply_text('Please provide a postcode.')
        return

    # Let the user know we're working on their request
    await update.message.reply_text(f"درحال جستجوی داروخانه‌ها برای کد پستی {postcode}...")

    try:
        # First progress update
        progress_msg = await update.message.reply_text("در حال جستجو... 🔍")

        pharmacy_ids = fetch_pharmacies_selenium(postcode)

        if not pharmacy_ids:
            await progress_msg.edit_text("هیچ داروخانه‌ای برای کد پستی داده شده پیدا نشد.")
            return

        # Update progress
        await progress_msg.edit_text(f"{len(pharmacy_ids)} داروخانه پیدا شد. درحال دریافت اطلاعات...")

        results = []
        total_pharmacies = len(pharmacy_ids)

        for idx, pharmacy_id in enumerate(pharmacy_ids, 1):
            if idx % 2 == 0:  # Update progress every 2 pharmacies
                await progress_msg.edit_text(f"دریافت اطلاعات ({idx}/{total_pharmacies})...")

            scraped_data = scrape_items_and_forms_selenium(pharmacy_id)
            if scraped_data:
                results.append(scraped_data)
            else:
                results.append(f"نتوانستم اطلاعات داروخانه با شناسه {pharmacy_id} را دریافت کنم.")

            # Add a small delay to avoid hitting rate limits
            await asyncio.sleep(0.5)

        # Format results
        response = "📊 نتایج (میانگین ۳ ماهه اخیر) 📊\n"
        for result in results:
            if isinstance(result, dict):
                response += (
                    f"\n🏥 داروخانه: {result['Pharmacy Name']} ({result['Pharmacy Postcode']})\n"
                    f"📦 اقلام توزیع شده: {result['Items']}\n"
                    f"📝 نسخه ها: {result['Forms']}\n"
                    f"🩺 CPCS: {result['CPCS']}\n"
                    f"💊 Pharmacy First: {result['Pharmacy First']}\n"
                    f"🔄 NMS: {result['NMS']}\n"
                    f"💻 EPS Takeup: {result['EPS Takeup']['Percentage']}\n"
                )
            else:
                response += f"{result}\n"

        # Delete the progress message and send the final results
        await progress_msg.delete()
        await update.message.reply_text(response)

    except Exception as e:
        logging.error(f"Error in handle_message: {e}")
        await update.message.reply_text("مشکلی در پردازش درخواست شما رخ داد. لطفاً دوباره تلاش کنید.")

async def telegram_bot_main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN environment variable is not set.")

    # For Heroku, use webhook if PORT is set
    port = int(os.environ.get('PORT', 5000))
    app_name = os.environ.get('APP_NAME')

    application = ApplicationBuilder().token(bot_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Add error handler
    application.add_error_handler(error_handler)

    # Use webhook if on Heroku (APP_NAME is set), otherwise use polling
    if app_name:
        # The webhook path needs to be fixed and consistent
        webhook_path = f"/{bot_token}"
        webhook_url = f"https://{app_name}.herokuapp.com{webhook_path}"

        logging.info(f"Starting webhook on port {port}")
        logging.info(f"Setting webhook URL: {webhook_url}")

        # Start the webhook server with the webhook URL
        await application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=webhook_path,  # Important: this must match the path in webhook_url
            webhook_url=webhook_url,  # Must provide a valid HTTPS URL here
            allowed_updates=["message", "callback_query"],
            close_loop=False  # Don't close the loop when done
        )
    else:
        logging.info("Starting polling")
        await application.run_polling(close_loop=False)  # Don't close the loop when done

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by updates."""
    logging.error(f"Update {update} caused error: {context.error}")

    # If update is available, send an error message
    if update and isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("Sorry, something went wrong. Please try again later.")

# Entry point
if __name__ == "__main__":
    # Setup for Windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Check if Chrome is available
    try:
        chrome_bin = os.environ.get('GOOGLE_CHROME_BIN', '/app/.apt/usr/bin/google-chrome')
        if os.path.exists(chrome_bin):
            logging.info(f"Chrome binary found at: {chrome_bin}")
        else:
            logging.warning(f"Chrome binary not found at expected path: {chrome_bin}")

        # Test Chrome initialization
        options = ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        driver = webdriver.Chrome(options=options)
        driver.quit()
        logging.info("Chrome initialization test successful")
    except Exception as e:
        logging.error(f"Chrome initialization test failed: {e}")

    # When imported as a module, don't run the bot directly
    # This section only runs if the file is executed directly as a script
    if os.environ.get('RUN_FROM_FILE') == 'true':
        try:
            logging.info("Starting Telegram bot directly from pharmacy_data.py...")
            # Use asyncio.run which properly manages the event loop
            asyncio.run(telegram_bot_main())
        except (KeyboardInterrupt, SystemExit):
            logging.info("Bot stopped by user.")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
