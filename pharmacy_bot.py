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

        # Set a shorter page load timeout for better performance
        driver.set_page_load_timeout(10)
        driver.set_script_timeout(5)

        # Use the correct search URL based on your information
        search_url = f"https://www.pharmdata.co.uk/search.php?query={postcode.replace(' ', '%20')}"
        logger.info(f"Using search URL: {search_url}")
        driver.get(search_url)

        # Use WebDriverWait instead of time.sleep for better performance
        WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

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

        # Set timeouts for better performance
        driver.set_page_load_timeout(10)
        driver.set_script_timeout(5)

        # Use the correct URL format for pharmacy details
        url = f"https://www.pharmdata.co.uk/nacs_select.php?query={pharmacy_id}"

        logger.info(f"Loading pharmacy details from: {url}")
        driver.get(url)

        # Use WebDriverWait instead of time.sleep for better performance
        WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Check if page loaded successfully
        page_source = driver.page_source
        if "not found" in page_source.lower() or "no results" in page_source.lower():
            logger.warning(f"Pharmacy not found: {pharmacy_id}")
            return None

        try:
            # Get pharmacy name - try different approaches
            try:
                # Try to find h1 or h2 elements first (likely to contain pharmacy name)
                for heading_tag in ["h1", "h2", "h3"]:
                    elements = driver.find_elements(By.TAG_NAME, heading_tag)
                    for element in elements:
                        text = element.text.strip()
                        if text and "pharmacy" in text.lower():
                            pharmacy_name = text
                            # Clean up name (remove codes in parentheses if present)
                            pharmacy_name = re.sub(r'\s*\([A-Z0-9]+\)\s*$', '', pharmacy_name)
                            logger.info(f"Found pharmacy name from heading: {pharmacy_name}")
                            break
                    else:
                        continue
                    break
                else:
                    # Try by class names
                    for class_name in [".panel-title-custom", ".pharmacy-name", ".panel-title", ".title"]:
                        try:
                            elements = driver.find_elements(By.CSS_SELECTOR, class_name)
                            if elements and elements[0].text.strip():
                                pharmacy_name = elements[0].text.strip()
                                pharmacy_name = re.sub(r'\s*\([A-Z0-9]+\)\s*$', '', pharmacy_name)
                                logger.info(f"Found pharmacy name from class {class_name}: {pharmacy_name}")
                                break
                        except:
                            pass
                    else:
                        # Last resort: look for pharmacy name pattern in page text
                        page_text = driver.find_element(By.TAG_NAME, "body").text
                        name_match = re.search(r'([A-Za-z0-9\s&]+\bPharmacy\b|Boots|Lloyds\s+Pharmacy|ASDA\s+Pharmacy|Superdrug)', page_text)
                        pharmacy_name = name_match.group(0) if name_match else f"Pharmacy {pharmacy_id}"
                        logger.info(f"Found pharmacy name from regex: {pharmacy_name}")
            except Exception as e:
                logger.warning(f"Error finding pharmacy name: {e}")
                pharmacy_name = f"Pharmacy {pharmacy_id}"

            # Get address and postcode from page text
            page_text = driver.find_element(By.TAG_NAME, "body").text

            # Try to find full address
            address = "Address not found"
            address_pattern = r'(?:ADDRESS|Address|address)[:\s]+(.*?)(?:\n|$)'
            address_match = re.search(address_pattern, page_text)
            if address_match:
                address = address_match.group(1).strip()
            else:
                # Try to find comma-separated address near pharmacy name
                if 'pharmacy_name' in locals():
                    try:
                        # Look for an address-like pattern (comma-separated text ending with postcode)
                        address_pattern = r'(?:' + re.escape(pharmacy_name) + r'.*?)([^,\n]+(?:,[^,\n]+){2,})'
                        address_match = re.search(address_pattern, page_text)
                        if address_match:
                            address = address_match.group(1).strip()
                    except:
                        pass

            # Extract postcode from address or find separately
            uk_postcode_pattern = r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b'
            postcode_match = re.search(uk_postcode_pattern, page_text)
            postcode = postcode_match.group(0) if postcode_match else "N/A"
            logger.info(f"Found postcode: {postcode}")

            # Now extract metrics based on what we know about PharmData
            # Extract metrics and rank information
            # PharmData shows metrics with rank patterns like: "0 (#11,367)"

            # Items
            items_value = "Registration Required"
            items_rank = "N/A"
            items_pattern = r'Items:?\s*(\d[\d,\.]*)\s*(?:\(#([\d,]+)\))?'
            items_match = re.search(items_pattern, page_text)
            if items_match:
                items_value = items_match.group(1)
                items_rank = items_match.group(2) if items_match.group(2) else "N/A"
                logger.info(f"Found items metric: {items_value} (Rank: {items_rank})")

            # Forms/Prescriptions
            forms_value = "Registration Required"
            forms_rank = "N/A"
            forms_pattern = r'(?:Forms|Prescriptions):?\s*(\d[\d,\.]*)\s*(?:\(#([\d,]+)\))?'
            forms_match = re.search(forms_pattern, page_text)
            if forms_match:
                forms_value = forms_match.group(1)
                forms_rank = forms_match.group(2) if forms_match.group(2) else "N/A"
                logger.info(f"Found forms metric: {forms_value} (Rank: {forms_rank})")

            # CPCS
            cpcs_value = "Registration Required"
            cpcs_rank = "N/A"
            cpcs_pattern = r'CPCS:?\s*(\d[\d,\.]*)\s*(?:\(#([\d,]+)\))?'
            cpcs_match = re.search(cpcs_pattern, page_text)
            if cpcs_match:
                cpcs_value = cpcs_match.group(1)
                cpcs_rank = cpcs_match.group(2) if cpcs_match.group(2) else "N/A"
                logger.info(f"Found CPCS metric: {cpcs_value} (Rank: {cpcs_rank})")

            # Pharmacy First
            pharmacy_first_value = "Registration Required"
            pharmacy_first_rank = "N/A"
            pf_pattern = r'(?:Pharmacy First|PF):?\s*(\d[\d,\.]*)\s*(?:\(#([\d,]+)\))?'
            pf_match = re.search(pf_pattern, page_text)
            if pf_match:
                pharmacy_first_value = pf_match.group(1)
                pharmacy_first_rank = pf_match.group(2) if pf_match.group(2) else "N/A"
                logger.info(f"Found Pharmacy First metric: {pharmacy_first_value} (Rank: {pharmacy_first_rank})")

            # NMS
            nms_value = "Registration Required"
            nms_rank = "N/A"
            nms_pattern = r'NMS:?\s*(\d[\d,\.]*)\s*(?:\(#([\d,]+)\))?'
            nms_match = re.search(nms_pattern, page_text)
            if nms_match:
                nms_value = nms_match.group(1)
                nms_rank = nms_match.group(2) if nms_match.group(2) else "N/A"
                logger.info(f"Found NMS metric: {nms_value} (Rank: {nms_rank})")

            # EPS Takeup
            eps_value = "Registration Required"
            eps_rank = "N/A"
            eps_pattern = r'(?:EPS|EPS Takeup|EPS Nominations):?\s*(\d+%)\s*(?:\(([\d,]+)[^)]*\))?'
            eps_match = re.search(eps_pattern, page_text)
            if eps_match:
                eps_value = eps_match.group(1)
                eps_rank = eps_match.group(2) if eps_match.group(2) else "N/A"
                logger.info(f"Found EPS metric: {eps_value} (Rank: {eps_rank})")

            # Look for JavaScript data arrays which might contain metrics
            try:
                # Execute JavaScript to get metrics if available
                script = """
                    var dataObj = {};
                    if (typeof figures !== 'undefined') {
                        dataObj.figures = figures;
                    }
                    if (typeof items !== 'undefined') {
                        dataObj.items = items;
                    }
                    if (typeof forms !== 'undefined') {
                        dataObj.forms = forms;
                    }
                    if (typeof cpcs !== 'undefined') {
                        dataObj.cpcs = cpcs;
                    }
                    if (typeof nms !== 'undefined') {
                        dataObj.nms = nms;
                    }
                    if (typeof eps !== 'undefined') {
                        dataObj.eps = eps;
                    }
                    return JSON.stringify(dataObj);
                """
                js_data = driver.execute_script(script)
                if js_data:
                    data_obj = json.loads(js_data)
                    logger.info(f"Found JavaScript data: {data_obj.keys()}")

                    # Extract metrics from JS data if available
                    if 'figures' in data_obj:
                        figures = data_obj['figures']
                        if figures and len(figures) > 0:
                            logger.info("Found figures array in JavaScript data")
                            # Process figures data if needed
            except Exception as e:
                logger.warning(f"Error extracting JavaScript data: {e}")

            # Build comprehensive pharmacy data object with all available information
            pharmacy_data = {
                'name': pharmacy_name,
                'address': address,
                'postcode': postcode,
                'items': f"{items_value} (Rank: {items_rank})" if items_value != "Registration Required" else "Registration Required",
                'forms': f"{forms_value} (Rank: {forms_rank})" if forms_value != "Registration Required" else "Registration Required",
                'cpcs': f"{cpcs_value} (Rank: {cpcs_rank})" if cpcs_value != "Registration Required" else "Registration Required",
                'pharmacy_first': f"{pharmacy_first_value} (Rank: {pharmacy_first_rank})" if pharmacy_first_value != "Registration Required" else "Registration Required",
                'nms': f"{nms_value} (Rank: {nms_rank})" if nms_value != "Registration Required" else "Registration Required",
                'eps': f"{eps_value} (Rank: {eps_rank})" if eps_value != "Registration Required" else "Registration Required"
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
                name_match = re.search(r'([A-Za-z0-9\s&]+\bPharmacy\b|Boots|Lloyds\s+Pharmacy|ASDA\s+Pharmacy|Superdrug)', page_text)
                pharmacy_name = name_match.group(0) if name_match else f"Pharmacy {pharmacy_id}"

                # Try to find postcode
                uk_postcode_pattern = r'\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b'
                postcode_match = re.search(uk_postcode_pattern, page_text)
                postcode = postcode_match.group(0) if postcode_match else "N/A"

                # Return minimal data with registration message
                return {
                    'name': pharmacy_name,
                    'address': "Address not found",
                    'postcode': postcode,
                    'items': "Registration Required",
                    'forms': "Registration Required",
                    'cpcs': "Registration Required",
                    'pharmacy_first': "Registration Required",
                    'nms': "Registration Required",
                    'eps': "Registration Required"
                }
            except Exception as fallback_error:
                logger.error(f"Fallback extraction failed: {fallback_error}")
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
        await update.message.reply_text(
            'Hello! I am a UK Pharmacy Information bot. 🏥\n\n'
            'Please enter a UK postcode to find pharmacies in your area.\n\n'
            'Note: Some detailed metrics require registration on PharmData.co.uk, '
            'but I will try to show you all available public information.'
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    try:
        await update.message.reply_text(
            '📋 *How to use this bot:*\n\n'
            '1. Simply enter a valid UK postcode (e.g., SW1A 1AA)\n'
            '2. I will find pharmacies in that area\n'
            '3. For each pharmacy, I will show:\n'
            '   • Pharmacy name and address\n'
            '   • Any available metrics (Items, Forms, CPCS, etc.)\n\n'
            '⚠️ *Please Note:* Some detailed metrics require registration on '
            'PharmData.co.uk. Public data will be shown where available.'
        )
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

        # Format the postcode correctly (uppercase, proper spacing)
        postcode = postcode.upper().strip()

        # More flexible validation of UK postcode with regex
        # This matches various formats and will help normalize them
        postcode_match = re.match(r'^([A-Z]{1,2}[0-9][A-Z0-9]?)[ -]?([0-9][A-Z]{2})$', postcode, re.IGNORECASE)

        if not postcode_match:
            await update.message.reply_text(
                "Please enter a valid UK postcode format (e.g. 'SW1A 1AA').\n"
                "Valid formats include 'SW1A 1AA', 'SW1A1AA', or 'sw1a 1aa'."
            )
            return

        # Normalize the postcode format to ensure proper spacing
        postcode = f"{postcode_match.group(1)} {postcode_match.group(2)}"
        logger.info(f"Normalized postcode: {postcode}")

        # Send initial status message
        status_msg = await update.message.reply_text("Searching for pharmacies... 🔍")

        # Create a task for searching pharmacies
        try:
            # Search for pharmacies with a timeout to prevent hanging
            task = asyncio.create_task(
                asyncio.to_thread(search_pharmacies, postcode)
            )
            # Wait for the task with timeout
            pharmacy_ids = await asyncio.wait_for(task, timeout=15)
        except asyncio.TimeoutError:
            await status_msg.edit_text("The search is taking too long. Please try again later.")
            return
        except Exception as e:
            logger.error(f"Error in pharmacy search: {e}")
            await status_msg.edit_text("An error occurred while searching. Please try again.")
            return

        if not pharmacy_ids:
            await status_msg.edit_text("No pharmacies found for the given postcode.")
            return

        await status_msg.edit_text(f"Found {len(pharmacy_ids)} pharmacies. Retrieving information...")

        # Get details for each pharmacy concurrently
        results = []
        tasks = []

        # Create tasks for all pharmacy details
        for pharmacy_id in pharmacy_ids[:3]:  # Limit to top 3 for better performance
            tasks.append(
                asyncio.create_task(
                    asyncio.to_thread(get_pharmacy_details, pharmacy_id)
                )
            )

        # Wait for all tasks to complete
        try:
            # Process completed tasks as they finish
            for completed_task in asyncio.as_completed(tasks, timeout=20):
                pharmacy = await completed_task
                if pharmacy:
                    results.append(pharmacy)
                    # Update status message
                    await status_msg.edit_text(f"Retrieved information for {len(results)}/{len(tasks)} pharmacies...")
        except asyncio.TimeoutError:
            logger.warning("Timeout getting pharmacy details")
            # Continue with any results we got
            if not results:
                await status_msg.edit_text("Timed out while retrieving pharmacy information.")
                return
        except Exception as e:
            logger.error(f"Error processing pharmacy details: {e}")
            # Continue with any results we got

        # Format and send results
        if results:
            response = "📊 Pharmacy Information 📊\n"

            for pharmacy in results:
                response += f"\n🏥 Pharmacy: {pharmacy['name']}\n"

                # Add address if available
                if 'address' in pharmacy and pharmacy['address'] != "Address not found":
                    response += f"📍 Address: {pharmacy['address']}\n"

                # Add postcode
                response += f"📮 Postcode: {pharmacy['postcode']}\n"

                # Add registration notice if all metrics require registration
                all_require_registration = all(
                    pharmacy.get(metric) == "Registration Required"
                    for metric in ['items', 'forms', 'cpcs', 'pharmacy_first', 'nms', 'eps']
                )

                if all_require_registration:
                    response += "\n⚠️ Full metrics data requires registration at PharmData.co.uk\n"
                else:
                    # Include metrics that have values
                    if pharmacy['items'] != "Registration Required":
                        response += f"📦 Items Dispensed: {pharmacy['items']}\n"

                    if pharmacy['forms'] != "Registration Required":
                        response += f"📝 Prescriptions: {pharmacy['forms']}\n"

                    if pharmacy['cpcs'] != "Registration Required":
                        response += f"🩺 CPCS: {pharmacy['cpcs']}\n"

                    if pharmacy['pharmacy_first'] != "Registration Required":
                        response += f"💊 Pharmacy First: {pharmacy['pharmacy_first']}\n"

                    if pharmacy['nms'] != "Registration Required":
                        response += f"🔄 NMS: {pharmacy['nms']}\n"

                    if pharmacy['eps'] != "Registration Required":
                        response += f"💻 EPS Takeup: {pharmacy['eps']}\n"

                    # Add note about other metrics requiring registration
                    response += "\n⚠️ Some metrics require registration at PharmData.co.uk\n"

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

    # Get port from environment for Heroku compatibility
    port = int(os.environ.get('PORT', 8443))

    logger.info("Starting bot with polling")

    # Create the application with appropriate settings
    application = (
        Application.builder()
        .token(bot_token)
        # Set higher concurrency for better performance
        .concurrent_updates(True)
        .build()
    )

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start the bot with polling (no webhook)
    try:
        logger.info("Starting bot with polling")
        application.run_polling(
            poll_interval=1.0,
            timeout=30,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

    logger.info("Bot stopped")

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
