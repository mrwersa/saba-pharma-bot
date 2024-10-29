from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys  # Import Keys to simulate key presses
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import asyncio
import nest_asyncio
import os  # Added import for environment variables
import re


# Apply nest_asyncio to allow nesting of asynchronous calls
nest_asyncio.apply()


# List of User-Agents to randomize
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
    
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15A372 Safari/604.1"
]


# Function to set up custom Chrome options for headless mode
def get_custom_chrome_options():
    chrome_options = ChromeOptions()
    
    # Run in headless mode
    chrome_options.add_argument("--headless")
    
    chrome_options.add_argument("--disable-gpu")
    
    chrome_options.add_argument("--no-sandbox")
    
    # Randomize User-Agent
    user_agent = random.choice(USER_AGENTS)
    
    chrome_options.add_argument(f"user-agent={user_agent}")
    
    # Set the path for Chrome binary and driver from environment variables
    chrome_options.binary_location = os.environ.get('GOOGLE_CHROME_BIN')
    
    return chrome_options


# Function to clear localStorage, sessionStorage, IndexedDB, and cache
def clear_browser_storage(driver):
    driver.execute_script("window.localStorage.clear();")
    
    driver.execute_script("window.sessionStorage.clear();")
    
    driver.execute_script("indexedDB.databases().then((dbs) => {dbs.forEach(db => indexedDB.deleteDatabase(db.name));});")
    
    driver.execute_script("caches.keys().then(function(names) { for (let name of names) caches.delete(name); });")


# Function to search using postcode and fetch all pharmacy IDs
def fetch_pharmacies_selenium(postcode):
    print(f"Searching PharmData for postcode: {postcode}")
    
    # Initialize Selenium WebDriver with custom Chrome options
    chrome_options = get_custom_chrome_options()
    
    driver = webdriver.Chrome(service=ChromeService(os.environ.get('CHROMEDRIVER_PATH')), options=chrome_options)
    
    try:
        # Step 1: Navigate to PharmData search page
        search_url = "https://www.pharmdata.co.uk"
        
        driver.get(search_url)
        
        # Step 2: Clear storage after the page has loaded
        clear_browser_storage(driver)
        
        # Step 3: Wait for the search bar to be present and input the postcode
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, 'query'))
        )
        
        search_box.send_keys(postcode)
        
        # Step 4: Simulate pressing the "Enter" key to submit the search
        search_box.send_keys(Keys.RETURN)
        
        print("Search results submitted, waiting for results to load.")
        
        # Step 5: Wait for all search results to load and collect all pharmacy IDs
        search_results = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'tr.search-result'))
        )
        
        pharmacy_ids = []
        
        for result in search_results:
            pharmacy_id = result.get_attribute('id')
            pharmacy_ids.append(pharmacy_id)
            
            # Limit to maximum 5 results
            if len(pharmacy_ids) >= 5:
                break
        
        if pharmacy_ids:
            print(f"Found {len(pharmacy_ids)} results.")
            return pharmacy_ids
        else:
            print("No pharmacy found for the given postcode")
            return None
    
    except Exception as e:
        print(f"An error occurred while fetching the pharmacy IDs: {e}")
        return None
    
    finally:
        driver.quit()


def scrape_items_and_forms_selenium(pharmacy_id):
    url = f"https://www.pharmdata.co.uk/nacs_select.php?query={pharmacy_id}"
    
    # Initialize Selenium WebDriver with custom Chrome options
    chrome_options = get_custom_chrome_options()
    
    driver = webdriver.Chrome(service=ChromeService(os.environ.get('CHROMEDRIVER_PATH')), options=chrome_options)
    
    try:
        # Step 1: Navigate to the pharmacy detail page
        driver.get(url)

        # Step 2: Clear storage after the page has loaded
        clear_browser_storage(driver)

        # Step 3: Take a screenshot of the current page
        screenshot_filename = f"pharmacy_{pharmacy_id}.png"
        
        driver.save_screenshot(screenshot_filename)

        # Step 4: Scrape all relevant data
        elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.list-group-item-text'))
        )

        # Extract the relevant data based on their positions on the page
        items_value = elements[0].text.split()[0]  # Items
        forms_value = elements[1].text.split()[0]  # Forms
        cpcs_value = elements[2].text.split()[0]   # CPCS
        pharmacy_first_value = elements[3].text.split()[0]  # Pharmacy First
        nms_value = elements[4].text.split()[0]    # NMS

        # EPS Takeup: Extract both percentage and raw number
        eps_takeup_value = elements[5].text  # Extract the full text (e.g., "96% 11078 (+18)")
        eps_takeup_percentage = eps_takeup_value.split('%')[0] + '%'  # Extract just the percentage (e.g., "96%")

        # Scrape the pharmacy name and address
        pharmacy_name_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.panel-title-custom'))
        )
        pharmacy_name = pharmacy_name_element.text.split('(')[0].strip()  # Extract pharmacy name

        # Get the full address from the parent element
        address_element = driver.find_element(By.XPATH, "//div[contains(@class, 'col-md-3')]")
        address_lines = address_element.text  # This gets all the text within the div, including the address

        # Use regex to extract postcode from the full address string
        postcode_match = re.search(r'\b[A-Z]{1,2}\d[A-Z]?\s*\d[A-Z]{2}\b', address_lines)
        postcode = postcode_match.group(0) if postcode_match else None

        # Return the scraped data along with the screenshot path
        return {
            'Items': items_value,
            'Forms': forms_value,
            'CPCS': cpcs_value,
            'Pharmacy First': pharmacy_first_value,
            'NMS': nms_value,
            'EPS Takeup': {
                'Percentage': eps_takeup_percentage
            },
            'Pharmacy Name': pharmacy_name,
            'Pharmacy Postcode': postcode,
            'Screenshot': screenshot_filename  # Include screenshot file path
        }

    except Exception as e:
        print(f"Error while scraping data: {e}")
        return None

    finally:
        driver.quit()


# Function to handle Telegram commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('سلام عزیزم! من ربات اطلاعات داروخانه هستم. لطفاً یک کد پستی بریتانیا وارد کن')


# This function will be called whenever a user sends a message
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    postcode = update.message.text.strip()  # Get the text message sent by the user
    
    if not postcode:
        await update.message.reply_text('Please provide a postcode.')
        return

    # Call the function to fetch pharmacy data using the entered postcode
    pharmacy_ids = fetch_pharmacies_selenium(postcode)
    
    if pharmacy_ids:
        await update.message.reply_text("Fetching results...")  # Show a message to indicate fetching
        
        results = []  # Store all scraped data here
        
        for pharmacy_id in pharmacy_ids:
            scraped_data = scrape_items_and_forms_selenium(pharmacy_id)
            
            if scraped_data:
                results.append(scraped_data)  # Store the scraped data
            else:
                results.append(f"Failed to scrape data for pharmacy ID: {pharmacy_id}")
        
        # Output all results after fetching
        response = "\n--- Results (Averages over 3 months) ---\n"  # Updated line
        
        for result in results:
            if isinstance(result, dict):
                response += (
                    f"\nPharmacy: {result['Pharmacy Name']} ({result['Pharmacy Postcode']})\n"
                    f"Items Dispensed: {result['Items']}\n"  # Updated line
                    f"Prescriptions: {result['Forms']}\n"  # Updated line
                    f"CPCS: {result['CPCS']}\n"  # Updated line
                    f"Pharmacy First: {result['Pharmacy First']}\n"  # Updated line
                    f"NMS: {result['NMS']}\n"  # Updated line
                    f"EPS Takeup: {result['EPS Takeup']['Percentage']}\n"  # Updated line
                )
                
                # Send the screenshot to the user
                with open(result['Screenshot'], 'rb') as photo:
                    await update.message.reply_photo(photo=photo)
                
                # Remove the screenshot file after sending
                os.remove(result['Screenshot'])

            else:
                response += f"{result}\n"  # Print error message if scraping failed for a specific pharmacy
                
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("No pharmacies found for the given postcode.")

async def telegram_bot_main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")  # Retrieve token from environment variable
    application = ApplicationBuilder().token(bot_token).build()  
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))  # Handle all text messages
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(telegram_bot_main())
