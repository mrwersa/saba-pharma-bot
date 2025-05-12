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
    chrome_options.binary_location = os.environ.get('GOOGLE_CHROME_BIN')
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
        print("Invalid postcode input.")
        return None

    chrome_options = get_custom_chrome_options()
    driver_path = os.environ.get('CHROMEDRIVER_PATH')
    if not driver_path:
        raise EnvironmentError("CHROMEDRIVER_PATH environment variable is not set.")

    try:
        driver = webdriver.Chrome(service=ChromeService(driver_path), options=chrome_options)
    except WebDriverException as e:
        print(f"WebDriver failed to start: {e}")
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
        print("Timeout while loading search results.")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
    finally:
        driver.quit()

def scrape_items_and_forms_selenium(pharmacy_id):
    if not pharmacy_id:
        print("No pharmacy ID provided.")
        return None

    chrome_options = get_custom_chrome_options()
    driver_path = os.environ.get('CHROMEDRIVER_PATH')
    if not driver_path:
        raise EnvironmentError("CHROMEDRIVER_PATH environment variable is not set.")

    try:
        driver = webdriver.Chrome(service=ChromeService(driver_path), options=chrome_options)
    except WebDriverException as e:
        print(f"WebDriver failed to start: {e}")
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
        print("Timed out while loading pharmacy details.")
        return None
    except Exception as e:
        print(f"Error while scraping data: {e}")
        return None
    finally:
        driver.quit()

# Telegram bot command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('سلام عزیزم! من ربات اطلاعات داروخانه هستم. لطفاً یک کد پستی بریتانیا وارد کن')

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    postcode = update.message.text.strip()

    if not postcode:
        await update.message.reply_text('Please provide a postcode.')
        return

    pharmacy_ids = fetch_pharmacies_selenium(postcode)

    if pharmacy_ids:
        await update.message.reply_text("Fetching results...")

        results = []

        for pharmacy_id in pharmacy_ids:
            scraped_data = scrape_items_and_forms_selenium(pharmacy_id)
            if scraped_data:
                results.append(scraped_data)
            else:
                results.append(f"Failed to scrape data for pharmacy ID: {pharmacy_id}")

        response = "\n--- Results (Averages over 3 months) ---\n"
        for result in results:
            if isinstance(result, dict):
                response += (
                    f"\nPharmacy: {result['Pharmacy Name']} ({result['Pharmacy Postcode']})\n"
                    f"Items Dispensed: {result['Items']}\n"
                    f"Prescriptions: {result['Forms']}\n"
                    f"CPCS: {result['CPCS']}\n"
                    f"Pharmacy First: {result['Pharmacy First']}\n"
                    f"NMS: {result['NMS']}\n"
                    f"EPS Takeup: {result['EPS Takeup']['Percentage']}\n"
                )
            else:
                response += f"{result}\n"

        await update.message.reply_text(response)
    else:
        await update.message.reply_text("No pharmacies found for the given postcode.")

async def telegram_bot_main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN environment variable is not set.")

    application = ApplicationBuilder().token(bot_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    await application.run_polling()

# Entry point
if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(telegram_bot_main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
