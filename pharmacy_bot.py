#!/usr/bin/env python
import os
import logging
import asyncio
import random
import re
import json
import time
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
try:
    load_dotenv()
except:
    pass

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
    options.add_argument("--window-size=1920,1080")  # Ensure large window size for seeing all elements
    # Use a realistic user agent
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    
    # Enable JavaScript
    options.add_argument("--enable-javascript")
    
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
    """Search for pharmacies by postcode using the correct search URL"""
    logger.info(f"Searching for pharmacies with postcode: {postcode}")
    options = setup_chrome()

    try:
        driver = webdriver.Chrome(options=options)

        # Use the correct search URL based on your information
        search_url = f"https://www.pharmdata.co.uk/search.php?query={postcode.replace(' ', '%20')}"
        logger.info(f"Using search URL: {search_url}")
        driver.get(search_url)
        time.sleep(3)  # Give time for page to load

        # Check if we have search results
        try:
            # Look for pharmacy codes in the search results
            # Pharmacy codes are typically 5-character alphanumeric codes like FQ560
            page_source = driver.page_source
            pharmacy_codes = re.findall(r'[A-Z][A-Z0-9]{4}', page_source)

            # Filter unique codes
            unique_codes = []
            for code in pharmacy_codes:
                if code not in unique_codes and len(code) == 5:
                    unique_codes.append(code)

            # Limit to first 5 unique pharmacy codes
            pharmacy_ids = unique_codes[:5]

            if pharmacy_ids:
                logger.info(f"Found {len(pharmacy_ids)} pharmacy codes: {pharmacy_ids}")
                return pharmacy_ids

            # If no codes found this way, try a different approach
            logger.info("No pharmacy codes found in page source, trying row search")

            # Look for rows that might contain pharmacy data
            rows = driver.find_elements(By.CSS_SELECTOR, "tr, .result-row, .pharmacy-row")
            logger.info(f"Found {len(rows)} potential result rows")

            pharmacy_ids = []
            for row in rows[:10]:  # Check first 10 rows
                try:
                    row_text = row.text
                    # Look for patterns that match pharmacy codes
                    codes = re.findall(r'[A-Z][A-Z0-9]{4}', row_text)
                    for code in codes:
                        if code not in pharmacy_ids:
                            pharmacy_ids.append(code)
                except Exception as e:
                    logger.error(f"Error extracting from row: {e}")

            # Limit to 5 pharmacies
            pharmacy_ids = pharmacy_ids[:5]

            if pharmacy_ids:
                logger.info(f"Found {len(pharmacy_ids)} pharmacy IDs from rows: {pharmacy_ids}")
                return pharmacy_ids

        except Exception as e:
            logger.warning(f"Error extracting search results: {e}")

        # If no results found with direct methods, try looking at links and anchor tags
        try:
            logger.info("Trying to find pharmacy codes in links")
            links = driver.find_elements(By.TAG_NAME, "a")
            logger.info(f"Found {len(links)} links on page")

            pharmacy_ids = []
            for link in links:
                try:
                    href = link.get_attribute("href") or ""
                    # Check for nacs_select.php links which indicate pharmacy
                    if "nacs_select.php?query=" in href:
                        pharmacy_id = href.split("nacs_select.php?query=")[1]
                        if pharmacy_id and pharmacy_id not in pharmacy_ids:
                            pharmacy_ids.append(pharmacy_id)

                    # Also check for pharmacy codes in link text
                    link_text = link.text
                    codes = re.findall(r'[A-Z][A-Z0-9]{4}', link_text)
                    for code in codes:
                        if code not in pharmacy_ids:
                            pharmacy_ids.append(code)
                except:
                    pass

            # Limit to 5 pharmacies
            pharmacy_ids = pharmacy_ids[:5]

            if pharmacy_ids:
                logger.info(f"Found {len(pharmacy_ids)} pharmacy IDs from links: {pharmacy_ids}")
                return pharmacy_ids

        except Exception as e:
            logger.warning(f"Error extracting from links: {e}")

        # If all else fails, just look for 5-character codes in the entire page text
        try:
            logger.info("Trying to find pharmacy codes in full page text")
            page_text = driver.find_element(By.TAG_NAME, "body").text

            # Advanced regex to find pharmacy codes but avoid false positives
            # Looking for codes that appear after "Code:" or in parentheses
            codes_with_context = re.findall(r'(?:Code:?\s*|ODS:?\s*|\()([A-Z][A-Z0-9]{4})(?:\)|\s|$)', page_text)
            if codes_with_context:
                pharmacy_ids = codes_with_context[:5]
                logger.info(f"Found {len(pharmacy_ids)} pharmacy IDs from context: {pharmacy_ids}")
                return pharmacy_ids

            # As a last resort, just find all 5-character codes
            all_codes = re.findall(r'[A-Z][A-Z0-9]{4}', page_text)
            unique_codes = []
            for code in all_codes:
                if code not in unique_codes and len(code) == 5:
                    unique_codes.append(code)

            if unique_codes:
                pharmacy_ids = unique_codes[:5]
                logger.info(f"Found {len(pharmacy_ids)} pharmacy IDs from full text: {pharmacy_ids}")
                return pharmacy_ids

        except Exception as e:
            logger.warning(f"Error extracting from full text: {e}")

        # If we get here, all search attempts failed
        logger.warning(f"All search attempts failed for postcode: {postcode}")
        return []

    except Exception as e:
        logger.error(f"Fatal error in search_pharmacies: {e}")
        return []
    finally:
        try:
            driver.quit()
        except:
            pass

def get_pharmacy_details(pharmacy_id):
    """Get details for a specific pharmacy using the correct nacs_select.php URL"""
    logger.info(f"Getting details for pharmacy ID: {pharmacy_id}")
    options = setup_chrome()

    try:
        driver = webdriver.Chrome(options=options)

        # Use the correct URL format for pharmacy details
        url = f"https://www.pharmdata.co.uk/nacs_select.php?query={pharmacy_id}"

        logger.info(f"Loading pharmacy details from: {url}")
        driver.get(url)
        time.sleep(3)  # Give time for page to load

        # Check if page loaded successfully
        page_source = driver.page_source
        if "not found" in page_source.lower() or "no results" in page_source.lower():
            logger.warning(f"Pharmacy not found: {pharmacy_id}")
            return None

        try:
            # 1. Get pharmacy name - using panel-title-custom class from your example
            try:
                name_element = driver.find_element(By.CSS_SELECTOR, ".panel-title-custom")
                pharmacy_name = name_element.text.strip()

                # Clean up name (remove codes in parentheses if present)
                pharmacy_name = re.sub(r'\s*\([A-Z0-9]+\)\s*$', '', pharmacy_name)
                logger.info(f"Found pharmacy name: {pharmacy_name}")
            except:
                # Try alternative selectors if panel-title-custom not found
                for selector in ["h1", "h2", ".pharmacy-name", ".panel-title"]:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements and elements[0].text.strip():
                            pharmacy_name = elements[0].text.strip()
                            pharmacy_name = re.sub(r'\s*\([A-Z0-9]+\)\s*$', '', pharmacy_name)
                            break
                    except:
                        pass
                else:
                    pharmacy_name = "Unknown Pharmacy"

            # 2. Get postcode - using regex on page text
            page_text = driver.find_element(By.TAG_NAME, "body").text
            uk_postcode_pattern = r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b'
            postcode_match = re.search(uk_postcode_pattern, page_text)
            postcode = postcode_match.group(0) if postcode_match else "N/A"
            logger.info(f"Found postcode: {postcode}")

            # 3. Get metrics - specifically using the list-group-item-text class from your example
            metrics = {}

            # Try to find the list-group-item-text elements which contain metrics
            try:
                metric_elements = driver.find_elements(By.CSS_SELECTOR, ".list-group-item-text")
                logger.info(f"Found {len(metric_elements)} metrics using list-group-item-text class")

                # Extract metrics based on position as shown in your example
                if len(metric_elements) >= 6:
                    # Items value (first element)
                    items_text = metric_elements[0].text
                    items_match = re.search(r'(\d[\d,\.]+)', items_text)
                    items_value = items_match.group(1) if items_match else "N/A"

                    # Forms value (second element)
                    forms_text = metric_elements[1].text
                    forms_match = re.search(r'(\d[\d,\.]+)', forms_text)
                    forms_value = forms_match.group(1) if forms_match else "N/A"

                    # CPCS value (third element)
                    cpcs_text = metric_elements[2].text
                    cpcs_match = re.search(r'(\d[\d,\.]+)', cpcs_text)
                    cpcs_value = cpcs_match.group(1) if cpcs_match else "N/A"

                    # Pharmacy First value (fourth element)
                    pf_text = metric_elements[3].text
                    pf_match = re.search(r'(\d[\d,\.]+)', pf_text)
                    pharmacy_first_value = pf_match.group(1) if pf_match else "N/A"

                    # NMS value (fifth element)
                    nms_text = metric_elements[4].text
                    nms_match = re.search(r'(\d[\d,\.]+)', nms_text)
                    nms_value = nms_match.group(1) if nms_match else "N/A"

                    # EPS value (sixth element)
                    eps_text = metric_elements[5].text
                    eps_match = re.search(r'(\d+)%', eps_text)
                    eps_takeup = eps_match.group(0) if eps_match else "N/A"

                    logger.info("Successfully extracted metrics from list-group-item-text elements")
                else:
                    logger.warning("Not enough list-group-item-text elements found")
                    items_value = forms_value = cpcs_value = pharmacy_first_value = nms_value = eps_takeup = "N/A"
            except Exception as e:
                logger.warning(f"Error extracting metrics from list-group-item-text: {e}")
                items_value = forms_value = cpcs_value = pharmacy_first_value = nms_value = eps_takeup = "N/A"

            # If any metric is still N/A, try looking for class names with ks- prefix (from your example)
            try:
                if items_value == "N/A":
                    items_element = driver.find_element(By.CSS_SELECTOR, ".ks-items")
                    items_text = items_element.text
                    items_match = re.search(r'(\d[\d,\.]+)', items_text)
                    if items_match:
                        items_value = items_match.group(1)

                if forms_value == "N/A":
                    forms_element = driver.find_element(By.CSS_SELECTOR, ".ks-forms")
                    forms_text = forms_element.text
                    forms_match = re.search(r'(\d[\d,\.]+)', forms_text)
                    if forms_match:
                        forms_value = forms_match.group(1)

                if cpcs_value == "N/A":
                    cpcs_element = driver.find_element(By.CSS_SELECTOR, ".ks-cpcs")
                    cpcs_text = cpcs_element.text
                    cpcs_match = re.search(r'(\d[\d,\.]+)', cpcs_text)
                    if cpcs_match:
                        cpcs_value = cpcs_match.group(1)

                if nms_value == "N/A":
                    nms_element = driver.find_element(By.CSS_SELECTOR, ".ks-nms")
                    nms_text = nms_element.text
                    nms_match = re.search(r'(\d[\d,\.]+)', nms_text)
                    if nms_match:
                        nms_value = nms_match.group(1)

                if eps_takeup == "N/A":
                    eps_element = driver.find_element(By.CSS_SELECTOR, ".ks-eps")
                    eps_text = eps_element.text
                    eps_match = re.search(r'(\d+)%', eps_text)
                    if eps_match:
                        eps_takeup = eps_match.group(0)
            except Exception as e:
                logger.warning(f"Error extracting metrics from ks- classes: {e}")

            # Build pharmacy data object
            pharmacy_data = {
                'name': pharmacy_name,
                'postcode': postcode,
                'items': items_value,
                'forms': forms_value,
                'cpcs': cpcs_value,
                'pharmacy_first': pharmacy_first_value,
                'nms': nms_value,
                'eps': eps_takeup
            }

            logger.info(f"Extracted pharmacy data: {pharmacy_data}")
            return pharmacy_data

        except Exception as e:
            logger.error(f"Error extracting pharmacy details: {e}")

            # Try a simple fallback approach - just get the name and postcode
            try:
                # Get page text for simple extraction
                page_text = driver.find_element(By.TAG_NAME, "body").text

                # Try to find pharmacy name
                name_match = re.search(r'([A-Za-z0-9\s&]+\bPharmacy\b|Boots|Lloyds\s+Pharmacy)', page_text)
                pharmacy_name = name_match.group(0) if name_match else "Unknown Pharmacy"

                # Try to find postcode
                uk_postcode_pattern = r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b'
                postcode_match = re.search(uk_postcode_pattern, page_text)
                postcode = postcode_match.group(0) if postcode_match else "N/A"

                # Return minimal data
                return {
                    'name': pharmacy_name,
                    'postcode': postcode,
                    'items': "N/A",
                    'forms': "N/A",
                    'cpcs': "N/A",
                    'pharmacy_first': "N/A",
                    'nms': "N/A",
                    'eps': "N/A"
                }
            except:
                return None

    except Exception as e:
        logger.error(f"Error getting pharmacy details: {e}")
        return None
    finally:
        try:
            driver.quit()
        except:
            pass

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
