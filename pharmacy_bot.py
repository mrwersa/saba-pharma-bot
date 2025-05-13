#!/usr/bin/env python
import os
import logging
import asyncio
import random
import re
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import nest_asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, WebDriverException

# Load environment variables
load_dotenv()

# Apply nest_asyncio for async operations
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# User agents for browser requests
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

# Chrome setup
def setup_chrome():
    """Configure Chrome options for Selenium"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    
    # Check for Chrome binary location
    for chrome_path in [
        os.environ.get('GOOGLE_CHROME_BIN'),
        '/app/.chrome-for-testing/chrome-linux64/chrome',
        '/app/.apt/usr/bin/google-chrome'
    ]:
        if chrome_path and os.path.exists(chrome_path):
            logger.info(f"Using Chrome binary at: {chrome_path}")
            options.binary_location = chrome_path
            break
            
    return options

# Web scraping functions
def search_pharmacies(postcode):
    """Search for pharmacies by postcode"""
    logger.info(f"Searching for pharmacies with postcode: {postcode}")
    options = setup_chrome()
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.get("https://www.pharmdata.co.uk")
        
        # Wait for search box and enter postcode
        search_box = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, 'query'))
        )
        search_box.clear()
        search_box.send_keys(postcode)
        search_box.send_keys(Keys.RETURN)
        
        # Get search results
        search_results = WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'tr.search-result'))
        )
        
        # Extract pharmacy IDs
        pharmacy_ids = [
            result.get_attribute('id') for result in search_results[:5] if result.get_attribute('id')
        ]
        
        return pharmacy_ids
    except Exception as e:
        logger.error(f"Error searching pharmacies: {e}")
        return []
    finally:
        driver.quit()

def get_pharmacy_details(pharmacy_id):
    """Get details for a specific pharmacy"""
    logger.info(f"Getting details for pharmacy ID: {pharmacy_id}")
    options = setup_chrome()
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(f"https://www.pharmdata.co.uk/nacs_select.php?query={pharmacy_id}")
        
        elements = WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.list-group-item-text'))
        )
        
        if len(elements) < 6:
            logger.warning(f"Insufficient data fields for pharmacy {pharmacy_id}")
            return None
            
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
            'name': pharmacy_name,
            'postcode': postcode,
            'items': items_value,
            'forms': forms_value,
            'cpcs': cpcs_value,
            'pharmacy_first': pharmacy_first_value,
            'nms': nms_value,
            'eps': eps_takeup_percentage
        }
    except Exception as e:
        logger.error(f"Error getting pharmacy details: {e}")
        return None
    finally:
        driver.quit()

# Telegram command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    try:
        logger.info(f"User {update.effective_user.id} started the bot")
        await update.message.reply_text('Hello! I am a Pharmacy Information bot. Please enter a UK postcode to find pharmacies.')
    except Exception as e:
        logger.error(f"Error in start command: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    try:
        await update.message.reply_text('To use this bot, simply enter a UK postcode and I will find pharmacies in that area.')
    except Exception as e:
        logger.error(f"Error in help command: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process user messages with postcodes"""
    try:
        user_id = update.effective_user.id
        postcode = update.message.text.strip()
        
        logger.info(f"Received message from user {user_id}: {postcode}")

        if not postcode:
            await update.message.reply_text("Please enter a valid postcode.")
            return

        # Send initial status message
        status_msg = await update.message.reply_text("Searching for pharmacies... 🔍")
        
        # Search for pharmacies
        pharmacy_ids = search_pharmacies(postcode)
        
        if not pharmacy_ids:
            await status_msg.edit_text("No pharmacies found for the given postcode.")
            return

        await status_msg.edit_text(f"Found {len(pharmacy_ids)} pharmacies. Retrieving information...")
        
        # Get details for each pharmacy
        results = []
        for idx, pharmacy_id in enumerate(pharmacy_ids, 1):
            # Update progress message
            if idx % 2 == 0:
                await status_msg.edit_text(f"Retrieving information ({idx}/{len(pharmacy_ids)})...")
                
            # Get pharmacy details
            pharmacy = get_pharmacy_details(pharmacy_id)
            if pharmacy:
                results.append(pharmacy)
                
            # Avoid hitting rate limits
            await asyncio.sleep(0.5)
            
        # Format and send results
        if results:
            response = "📊 Results (3-Month Averages) 📊\n"

            for pharmacy in results:
                response += (
                    f"\n🏥 Pharmacy: {pharmacy['name']} ({pharmacy['postcode']})\n"
                    f"📦 Items Dispensed: {pharmacy['items']}\n"
                    f"📝 Prescriptions: {pharmacy['forms']}\n"
                    f"🩺 CPCS: {pharmacy['cpcs']}\n"
                    f"💊 Pharmacy First: {pharmacy['pharmacy_first']}\n"
                    f"🔄 NMS: {pharmacy['nms']}\n"
                    f"💻 EPS Takeup: {pharmacy['eps']}\n"
                )

            # Delete status message and send results
            await status_msg.delete()
            await update.message.reply_text(response)
        else:
            await status_msg.edit_text("Sorry, I couldn't retrieve information about the pharmacies.")
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await update.message.reply_text("An error occurred while processing your request. Please try again.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates"""
    logger.error(f"Update {update} caused error: {context.error}")

def main():
    """Main function to start the bot"""
    # Get the Telegram bot token
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("No TELEGRAM_BOT_TOKEN provided in environment variables")
        return
        
    logger.info("Starting bot with polling")
    
    # Create the application
    application = Application.builder().token(bot_token).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot with polling (no webhook)
    application.run_polling(poll_interval=1.0)

# Entry point
if __name__ == "__main__":
    # Test Chrome setup on startup
    try:
        options = setup_chrome()
        driver = webdriver.Chrome(options=options)
        driver.quit()
        logger.info("Chrome initialization test successful")
    except Exception as e:
        logger.error(f"Chrome initialization failed: {e}")
    
    # Start the bot
    main()
