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
    """Search for pharmacies by postcode using multiple strategies"""
    logger.info(f"Searching for pharmacies with postcode: {postcode}")
    options = setup_chrome()
    
    try:
        driver = webdriver.Chrome(options=options)
        
        # First approach - Direct search URL
        direct_search_url = f"https://www.pharmdata.co.uk/search.php?query={postcode.replace(' ', '+')}"
        logger.info(f"Trying direct search URL: {direct_search_url}")
        driver.get(direct_search_url)
        time.sleep(3)  # Give time for JavaScript to execute
        
        # Check current URL - if redirected to a pharmacy, extract ID
        current_url = driver.current_url
        pharmacy_id_match = re.search(r'/pharmacy/([A-Z0-9]+)', current_url)
        if pharmacy_id_match:
            pharmacy_id = pharmacy_id_match.group(1)
            logger.info(f"Redirected directly to pharmacy: {pharmacy_id}")
            return [pharmacy_id]
        
        # Second approach - try to get results from the search page
        try:
            # Look for search results in the page
            results = []
            
            # Try multiple selectors to find result elements
            result_selectors = [
                ".tt-suggestion", 
                ".pharmacy-result", 
                "table.table tr", 
                "a[href*='pharmacy']"
            ]
            
            for selector in result_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    results = elements
                    logger.info(f"Found {len(results)} results using selector: {selector}")
                    break
            
            # Find pharmacy IDs from results
            pharmacy_ids = []
            for result in results[:5]:  # Limit to first 5 results
                try:
                    # Check for href attribute - might contain pharmacy ID
                    href = result.get_attribute("href") or ""
                    href_match = re.search(r'/pharmacy/([A-Z0-9]+)', href)
                    if href_match:
                        pharmacy_ids.append(href_match.group(1))
                        continue
                        
                    # Check for onclick attribute
                    onclick = result.get_attribute("onclick") or ""
                    onclick_match = re.search(r'/pharmacy/([A-Z0-9]+)', onclick)
                    if onclick_match:
                        pharmacy_ids.append(onclick_match.group(1))
                        continue
                    
                    # Check for ODS code in text content
                    text = result.text
                    ods_match = re.search(r'\(([A-Z][A-Z0-9]{4,5})\)', text)
                    if ods_match:
                        pharmacy_ids.append(ods_match.group(1))
                        continue
                except Exception as e:
                    logger.error(f"Error extracting from result: {e}")
            
            if pharmacy_ids:
                logger.info(f"Found {len(pharmacy_ids)} pharmacy IDs on search page")
                return pharmacy_ids
                
        except Exception as e:
            logger.warning(f"Error extracting search results: {e}")
        
        # Third approach - use bloodhound API directly
        try:
            logger.info("Trying bloodhound API search")
            driver.get(f"https://www.pharmdata.co.uk/bloodhound.php?q={postcode.replace(' ', '+')}")
            
            # Check if result is JSON
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                if body_text.startswith("[") and "]" in body_text:
                    # Parse JSON
                    data = json.loads(body_text)
                    
                    # Find pharmacy entries
                    pharmacy_ids = []
                    for item in data:
                        if isinstance(item, dict) and ('type' in item and item['type'] == 'pharmacy'):
                            if 'nacs' in item:
                                pharmacy_ids.append(item['nacs'])
                            elif 'id' in item:
                                pharmacy_ids.append(item['id'])
                    
                    if pharmacy_ids:
                        logger.info(f"Found {len(pharmacy_ids)} pharmacy IDs from API")
                        return pharmacy_ids
            except Exception as e:
                logger.warning(f"Failed to parse API response: {e}")
        except Exception as e:
            logger.warning(f"API search failed: {e}")
        
        # Fourth approach - try a hardcoded search with the site's search input
        try:
            logger.info("Trying manual search with postcode")
            driver.get("https://www.pharmdata.co.uk")
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Find search input - try multiple possible selectors
            search_input = None
            for selector in [
                "input.typeahead",
                "#pharmdata-search input",
                "input[type='search']",
                "input[name='q']"
            ]:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        search_input = elements[0]
                        logger.info(f"Found search input with selector: {selector}")
                        break
                except:
                    pass
            
            if not search_input:
                logger.warning("Could not find search input")
                return []
            
            # Enter postcode and submit
            search_input.clear()
            search_input.send_keys(postcode)
            search_input.send_keys(Keys.RETURN)
            
            # Wait for results
            time.sleep(3)
            
            # Check if we've been redirected to a pharmacy page
            current_url = driver.current_url
            pharmacy_id_match = re.search(r'/pharmacy/([A-Z0-9]+)', current_url)
            if pharmacy_id_match:
                pharmacy_id = pharmacy_id_match.group(1)
                logger.info(f"Redirected to pharmacy: {pharmacy_id}")
                return [pharmacy_id]
                
            # Otherwise, look for pharmacy links on the page
            pharmacy_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/pharmacy/']")
            
            if pharmacy_links:
                pharmacy_ids = []
                for link in pharmacy_links[:5]:
                    href = link.get_attribute("href") or ""
                    match = re.search(r'/pharmacy/([A-Z0-9]+)', href)
                    if match:
                        pharmacy_ids.append(match.group(1))
                
                if pharmacy_ids:
                    logger.info(f"Found {len(pharmacy_ids)} pharmacy IDs from links")
                    return pharmacy_ids
        
        except Exception as e:
            logger.warning(f"Manual search failed: {e}")
        
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
    """Get details for a specific pharmacy"""
    logger.info(f"Getting details for pharmacy ID: {pharmacy_id}")
    options = setup_chrome()
    
    try:
        driver = webdriver.Chrome(options=options)
        
        # Try both possible URL formats
        urls = [
            f"https://www.pharmdata.co.uk/pharmacy/{pharmacy_id}",
            f"https://www.pharmdata.co.uk/nacs_select.php?query={pharmacy_id}"
        ]
        
        loaded = False
        for url in urls:
            try:
                logger.info(f"Trying URL: {url}")
                driver.get(url)
                time.sleep(2)  # Wait for page to load
                
                # Check if page loaded successfully (contains pharmacy data)
                page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                if "not found" in page_text or "error" in page_text or "no results" in page_text:
                    logger.warning(f"Page error or no results at {url}")
                    continue
                
                # If we see pharmacy-related terms, consider it loaded
                if "pharmacy" in page_text or "dispensing" in page_text or "prescriptions" in page_text:
                    loaded = True
                    logger.info(f"Successfully loaded pharmacy page at {url}")
                    break
            except Exception as e:
                logger.warning(f"Error loading {url}: {e}")
        
        if not loaded:
            logger.error(f"Could not load pharmacy page for ID: {pharmacy_id}")
            return None
        
        # Extract pharmacy data
        try:
            # 1. Try to get pharmacy name
            name_selectors = [
                "h1", "h2.pharmacy-name", ".pharmacy-name", ".pharmacy-title", 
                ".panel-title", ".header-title"
            ]
            
            pharmacy_name = "Unknown Pharmacy"
            for selector in name_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and elements[0].text.strip():
                    pharmacy_name = elements[0].text.strip()
                    # Clean up name (remove codes in parentheses if present)
                    pharmacy_name = re.sub(r'\s*\([A-Z0-9]+\)\s*$', '', pharmacy_name)
                    logger.info(f"Found pharmacy name: {pharmacy_name}")
                    break
            
            # 2. Try to get postcode
            address_selectors = [
                ".address", "address", ".pharmacy-address", ".panel-body"
            ]
            
            postcode = "N/A"
            for selector in address_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    address_text = elements[0].text
                    uk_postcode_pattern = r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b'
                    match = re.search(uk_postcode_pattern, address_text)
                    if match:
                        postcode = match.group(0)
                        logger.info(f"Found postcode: {postcode}")
                        break
            
            # If still no postcode, try the whole page
            if postcode == "N/A":
                page_text = driver.find_element(By.TAG_NAME, "body").text
                uk_postcode_pattern = r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b'
                match = re.search(uk_postcode_pattern, page_text)
                if match:
                    postcode = match.group(0)
            
            # 3. Extract pharmacy metrics
            metrics = {}
            
            # Find all elements that might contain metrics
            metric_elements = []
            metric_selectors = [
                ".list-group-item", ".data-item", ".metric", ".stat-item",
                ".card", "table td", ".panel-body div"
            ]
            
            for selector in metric_selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                metric_elements.extend(elements)
            
            logger.info(f"Found {len(metric_elements)} potential metric elements")
            
            # Try to identify metrics by keywords in the text
            items_value = forms_value = cpcs_value = pharmacy_first_value = nms_value = eps_takeup = "N/A"
            
            for element in metric_elements:
                try:
                    text = element.text.lower().strip()
                    if not text:
                        continue
                    
                    # Items dispensed
                    if "item" in text and not "items_value" in locals():
                        match = re.search(r'(\d[\d,\.]+)', text)
                        if match:
                            items_value = match.group(1)
                    
                    # Forms/prescriptions
                    if ("form" in text or "prescription" in text) and not "forms_value" in locals():
                        match = re.search(r'(\d[\d,\.]+)', text)
                        if match:
                            forms_value = match.group(1)
                    
                    # CPCS
                    if "cpcs" in text and not "cpcs_value" in locals():
                        match = re.search(r'(\d[\d,\.]+)', text)
                        if match:
                            cpcs_value = match.group(1)
                    
                    # Pharmacy First
                    if "pharmacy first" in text and not "pharmacy_first_value" in locals():
                        match = re.search(r'(\d[\d,\.]+)', text)
                        if match:
                            pharmacy_first_value = match.group(1)
                    
                    # NMS
                    if "nms" in text and not "nms_value" in locals():
                        match = re.search(r'(\d[\d,\.]+)', text)
                        if match:
                            nms_value = match.group(1)
                    
                    # EPS
                    if "eps" in text and not "eps_takeup" in locals():
                        match = re.search(r'(\d[\d,\.]+)\s*%', text)
                        if match:
                            eps_takeup = match.group(0)
                except:
                    continue
            
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
