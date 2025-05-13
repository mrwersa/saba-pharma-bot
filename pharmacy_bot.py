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
    """Configure Chrome options for Selenium optimized for performance on Heroku"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=TranslateUI,BlinkGenPropertyTrees")
    options.add_argument("--disable-site-isolation-trials")
    options.add_argument("--disable-application-cache")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--window-size=800,600")  # Smaller window for faster rendering

    # Reduce memory usage
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-3d-apis")
    options.add_argument("--disable-ipc-flooding-protection")

    # Use a realistic user agent but don't randomize (for caching benefits)
    options.add_argument(f"user-agent={USER_AGENTS[0]}")

    # Enable JavaScript but with optimizations
    options.add_argument("--enable-javascript")
    options.add_argument("--disable-blink-features=AutomationControlled")

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

    # Always attempt to retrieve real pharmacy data from the website
    # No fallbacks or hardcoded data

    try:
        driver = webdriver.Chrome(options=options)

        # Set shorter timeouts to prevent hangs on Heroku
        driver.set_page_load_timeout(8)
        driver.set_script_timeout(5)

        # Try with a simpler, more reliable direct search URL
        try:
            # Use the correct search URL based on tested format
            search_url = f"https://www.pharmdata.co.uk/search.php?query={postcode.replace(' ', '+')}"
            logger.info(f"Using search URL: {search_url}")

            # Use a try-except block to handle timeouts during page load
            try:
                driver.get(search_url)
                # Wait for minimum page content to appear
                WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except TimeoutException:
                logger.warning("Initial page load timed out, continuing with partial page...")
                # Continue anyway as we might have partial content
        except Exception as e:
            logger.warning(f"Error during initial page load: {e}")
        
        # Debug info for troubleshooting search issues
        try:
            logger.info(f"Page title: {driver.title}")
            page_text_sample = driver.find_element(By.TAG_NAME, "body").text[:500]
            logger.info(f"Page text sample: {page_text_sample}")
            
            # Save page source to see what's happening
            page_source = driver.page_source
            logger.info(f"Page source length: {len(page_source)}")
            logger.info(f"Source sample: {page_source[:200]}...")
        except:
            pass

        # ATTEMPT 1: Check for pharmacy rows or tables
        pharmacy_ids = []
        try:
            # Look for common table structures or divs that might contain pharmacy listings
            selectors = ["table tr", ".pharmacy-item", ".search-result", "tr", "li"]
            for selector in selectors:
                rows = driver.find_elements(By.CSS_SELECTOR, selector)
                if rows:
                    logger.info(f"Found {len(rows)} potential elements with selector: {selector}")
                    for row in rows[:15]:  # Check first 15 rows
                        try:
                            row_text = row.text
                            if row_text:
                                # Look for pharmacy code pattern in row text
                                codes = re.findall(r'[A-Z][A-Z0-9]{4}', row_text)
                                for code in codes:
                                    if code not in pharmacy_ids and len(code) == 5:
                                        pharmacy_ids.append(code)
                                        logger.info(f"Found pharmacy code in row: {code}")
                        except Exception as e:
                            logger.debug(f"Error processing row: {e}")

            if pharmacy_ids:
                logger.info(f"Found {len(pharmacy_ids)} pharmacy codes from rows: {pharmacy_ids}")
                return pharmacy_ids[:5]
        except Exception as e:
            logger.warning(f"Error finding rows: {e}")

        # ATTEMPT 2: Check for links specifically containing pharmacy detail URLs
        try:
            links = driver.find_elements(By.TAG_NAME, "a")
            logger.info(f"Found {len(links)} links on page")
            
            for link in links:
                try:
                    href = link.get_attribute("href") or ""
                    
                    # Check for links to pharmacy details
                    if any(pattern in href for pattern in ["nacs_select.php", "pharmacy", "detail", "profile"]):
                        logger.info(f"Found pharmacy link: {href}")
                        
                        # Extract pharmacy ID from URL
                        if "query=" in href:
                            pharmacy_id = href.split("query=")[1].split("&")[0]
                            if pharmacy_id and len(pharmacy_id) == 5 and pharmacy_id not in pharmacy_ids:
                                pharmacy_ids.append(pharmacy_id)
                                logger.info(f"Extracted pharmacy ID from link: {pharmacy_id}")
                        
                        # Also check link text for codes
                        link_text = link.text
                        if link_text:
                            codes = re.findall(r'[A-Z][A-Z0-9]{4}', link_text)
                            for code in codes:
                                if code not in pharmacy_ids and len(code) == 5:
                                    pharmacy_ids.append(code)
                                    logger.info(f"Found pharmacy code in link text: {code}")
                except Exception as e:
                    logger.debug(f"Error processing link: {e}")
            
            if pharmacy_ids:
                logger.info(f"Found {len(pharmacy_ids)} pharmacy IDs from links: {pharmacy_ids}")
                return pharmacy_ids[:5]
                
        except Exception as e:
            logger.warning(f"Error processing links: {e}")

        # ATTEMPT 3: Extract all possible ODS codes from the entire page
        try:
            # Get the entire page source for more comprehensive search
            page_source = driver.page_source
            
            # Look for ODS codes (pattern: FQ560, FA123, etc.) in various contexts
            # 1. Direct ODS code extraction
            ods_patterns = [
                r'ODS Code[:\s]*([A-Z][A-Z0-9]{4})',  # ODS Code: FQ123
                r'Code[:\s]*([A-Z][A-Z0-9]{4})',      # Code: FQ123
                r'\(([A-Z][A-Z0-9]{4})\)',            # (FQ123)
                r'>([A-Z][A-Z0-9]{4})<',              # >FQ123<
                r'["\']([A-Z][A-Z0-9]{4})["\']',      # "FQ123" or 'FQ123'
                r'[^A-Z]([A-Z][A-Z0-9]{4})[^A-Z0-9]'  # General pattern with boundaries
            ]
            
            all_potential_codes = []
            
            for pattern in ods_patterns:
                matches = re.findall(pattern, page_source)
                all_potential_codes.extend(matches)
            
            # Use the page text as well for additional context
            page_text = driver.find_element(By.TAG_NAME, "body").text
            
            # Extract pharmacy names to help validate codes
            pharmacy_names = re.findall(r'([A-Za-z\s&]+(?:Pharmacy|PHARMACY|chemist|CHEMIST))', page_text)
            if pharmacy_names:
                logger.info(f"Found potential pharmacy names: {pharmacy_names[:3]}...")
            
            # Final attempt - just get all 5-character codes matching ODS pattern
            all_codes = re.findall(r'\b([A-Z][A-Z0-9]{4})\b', page_text)
            all_potential_codes.extend(all_codes)
            
            # Filter unique valid codes
            unique_codes = []
            for code in all_potential_codes:
                if code not in unique_codes and len(code) == 5:
                    # Validate to avoid false positives (like HTML tags)
                    if re.match(r'^[A-Z][A-Z0-9]{4}$', code) and code not in ['CLASS', 'WIDTH', 'HTTPS']:
                        unique_codes.append(code)
            
            if unique_codes:
                logger.info(f"Found {len(unique_codes)} potential pharmacy codes: {unique_codes}")
                return unique_codes[:5]  # Limit to 5
                
        except Exception as e:
            logger.warning(f"Error in final extraction attempt: {e}")

        # ATTEMPT 4: Try directly constructing pharmacy detail URLs
        try:
            logger.info("Attempting direct pharmacy detail page access")
            
            # Try clicking on search results rows
            rows = driver.find_elements(By.CSS_SELECTOR, "tr, li, .pharmacy-item")
            for row in rows[:10]:  # Try first 10 rows
                try:
                    # Try to click the row or find clickable elements inside it
                    clickable = row.find_elements(By.TAG_NAME, "a")
                    if clickable:
                        href = clickable[0].get_attribute("href")
                        if href and "nacs_select.php" in href:
                            # Extract pharmacy code from URL
                            if "query=" in href:
                                code = href.split("query=")[1].split("&")[0]
                                if code and len(code) == 5 and code not in pharmacy_ids:
                                    pharmacy_ids.append(code)
                                    logger.info(f"Found pharmacy code from clickable: {code}")
                except Exception as e:
                    logger.debug(f"Error processing clickable: {e}")
            
            if pharmacy_ids:
                logger.info(f"Found {len(pharmacy_ids)} pharmacy IDs from clickables: {pharmacy_ids}")
                return pharmacy_ids[:5]
                
        except Exception as e:
            logger.warning(f"Error in clickable approach: {e}")

        # ATTEMPT 5: Try a workaround by submitting search again with JavaScript
        try:
            logger.info("Attempting JavaScript-based search")
            # Execute search script
            driver.execute_script("""
                const searchInputs = document.querySelectorAll('input[type="search"], input[name="search"], input[placeholder*="search"]');
                if (searchInputs.length > 0) {
                    searchInputs[0].value = arguments[0];
                    const form = searchInputs[0].closest('form');
                    if (form) form.submit();
                }
            """, postcode)
            
            # Wait for results
            WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Try extraction again
            page_source = driver.page_source
            all_codes = re.findall(r'[A-Z][A-Z0-9]{4}', page_source)
            
            unique_codes = []
            for code in all_codes:
                if code not in unique_codes and len(code) == 5 and code not in ['CLASS', 'WIDTH', 'HTTPS']:
                    unique_codes.append(code)
            
            if unique_codes:
                logger.info(f"Found {len(unique_codes)} codes with JS approach: {unique_codes}")
                return unique_codes[:5]
                
        except Exception as e:
            logger.warning(f"JavaScript search approach failed: {e}")

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

        # Set shorter timeouts for better performance on Heroku
        driver.set_page_load_timeout(8)
        driver.set_script_timeout(5)

        # Use the correct URL format for pharmacy details
        url = f"https://www.pharmdata.co.uk/nacs_select.php?query={pharmacy_id}"

        logger.info(f"Loading pharmacy details from: {url}")
        try:
            driver.get(url)
            # Use a shorter timeout for the page load
            WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            logger.warning(f"Details page load timed out for {pharmacy_id}, continuing with partial content...")
            # Continue with whatever content we have

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
            
            # Items
            items_value = "0"
            items_rank = "N/A"
            items_pattern = r'(?:Items|Items Dispensed)[:\s]*([0-9,\.]+)[^\(]*(?:\(#([0-9,]+)\))?'
            items_match = re.search(items_pattern, page_text)
            if items_match:
                items_value = items_match.group(1)
                items_rank = items_match.group(2) if items_match.group(2) else "N/A"
                logger.info(f"Found items metric: {items_value} (Rank: {items_rank})")
            
            # Forms/Prescriptions
            forms_value = "0"
            forms_rank = "N/A"
            forms_pattern = r'(?:Forms|Prescriptions)[:\s]*([0-9,\.]+)[^\(]*(?:\(#([0-9,]+)\))?'
            forms_match = re.search(forms_pattern, page_text)
            if forms_match:
                forms_value = forms_match.group(1)
                forms_rank = forms_match.group(2) if forms_match.group(2) else "N/A"
                logger.info(f"Found forms metric: {forms_value} (Rank: {forms_rank})")
            
            # CPCS
            cpcs_value = "0" 
            cpcs_rank = "N/A"
            cpcs_pattern = r'CPCS[:\s]*([0-9,\.]+)[^\(]*(?:\(#([0-9,]+)\))?'
            cpcs_match = re.search(cpcs_pattern, page_text)
            if cpcs_match:
                cpcs_value = cpcs_match.group(1)
                cpcs_rank = cpcs_match.group(2) if cpcs_match.group(2) else "N/A"
                logger.info(f"Found CPCS metric: {cpcs_value} (Rank: {cpcs_rank})")
            
            # Pharmacy First
            pharmacy_first_value = "0"
            pharmacy_first_rank = "N/A"
            pf_pattern = r'(?:Pharmacy First|PF)[:\s]*([0-9,\.]+)[^\(]*(?:\(#([0-9,]+)\))?'
            pf_match = re.search(pf_pattern, page_text)
            if pf_match:
                pharmacy_first_value = pf_match.group(1)
                pharmacy_first_rank = pf_match.group(2) if pf_match.group(2) else "N/A"
                logger.info(f"Found Pharmacy First metric: {pharmacy_first_value} (Rank: {pharmacy_first_rank})")
            
            # NMS
            nms_value = "0"
            nms_rank = "N/A"
            nms_pattern = r'NMS[:\s]*([0-9,\.]+)[^\(]*(?:\(#([0-9,]+)\))?'
            nms_match = re.search(nms_pattern, page_text)
            if nms_match:
                nms_value = nms_match.group(1)
                nms_rank = nms_match.group(2) if nms_match.group(2) else "N/A"
                logger.info(f"Found NMS metric: {nms_value} (Rank: {nms_rank})")
            
            # EPS Takeup
            eps_value = "0%"
            eps_rank = "N/A"
            eps_pattern = r'(?:EPS|EPS Takeup|EPS Nominations)[:\s]*([0-9]+%)[^\(]*(?:\(#?([0-9,]+)[^)]*\))?'
            eps_match = re.search(eps_pattern, page_text)
            if eps_match:
                eps_value = eps_match.group(1)
                eps_rank = eps_match.group(2) if eps_match.group(2) else "N/A"
                logger.info(f"Found EPS metric: {eps_value} (Rank: {eps_rank})")
            
            # Try to find additional data in JavaScript
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
            except Exception as e:
                logger.warning(f"Error extracting JavaScript data: {e}")

            # Build comprehensive pharmacy data object with all available information
            pharmacy_data = {
                'name': pharmacy_name,
                'address': address,
                'postcode': postcode,
                'items': f"{items_value}",
                'forms': f"{forms_value}",
                'cpcs': f"{cpcs_value}",
                'pharmacy_first': f"{pharmacy_first_value}",
                'nms': f"{nms_value}",
                'eps': f"{eps_value}"
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

                # Return basic data
                return {
                    'name': pharmacy_name,
                    'address': "Address not found",
                    'postcode': postcode,
                    'items': "0",
                    'forms': "0",
                    'cpcs': "0",
                    'pharmacy_first': "0",
                    'nms': "0",
                    'eps': "0%"
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
            'I will show you metrics like Items, Prescriptions, CPCS, Pharmacy First, NMS, and EPS Takeup.'
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    try:
        await update.message.reply_text(
            '📋 *How to use this bot:*\n\n'
            '🔎 *Search by postcode:*\n'
            '1. Enter a valid UK postcode (e.g., SW1A 1AA)\n'
            '2. I will find pharmacies in that area\n\n'
            '🔢 *Direct lookup:*\n'
            'You can also enter a specific pharmacy ODS code\n'
            '(e.g., FJ144) if you already know it\n\n'
            '📊 *Information shown:*\n'
            '• Pharmacy name and address\n'
            '• Available pharmacy services'
        )
    except Exception as e:
        logger.error(f"Error in help command: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process user messages with postcodes or direct pharmacy codes"""
    try:
        user_id = update.effective_user.id
        user_input = update.message.text.strip()

        logger.info(f"Received message from user {user_id}: {user_input}")

        # Check if it's a direct pharmacy ODS code (format like FA123, FQ456)
        if re.match(r'^[A-Z][A-Z0-9]{4}$', user_input, re.IGNORECASE):
            pharmacy_id = user_input.upper()
            logger.info(f"Direct pharmacy ODS code detected: {pharmacy_id}")

            # Send status message
            status_msg = await update.message.reply_text(f"Looking up pharmacy with code {pharmacy_id}...")

            # Get pharmacy details directly
            try:
                # Use a separate thread for the pharmacy details lookup
                pharmacy = await asyncio.to_thread(get_pharmacy_details, pharmacy_id)

                if pharmacy:
                    # Format the single pharmacy result - check if it's Boots
                    if "Boots" in pharmacy['name']:
                        response = "📊 Boots Pharmacy Information 📊\n"
                    else:
                        response = "📊 Pharmacy Information 📊\n"

                    # No separator needed for single result
                    response += f"\n🏥 Pharmacy: {pharmacy['name']}\n"

                    # Add address if available
                    if 'address' in pharmacy and pharmacy['address'] != "Address not found":
                        response += f"📍 Address: {pharmacy['address']}\n"

                    # Add postcode
                    response += f"📮 Postcode: {pharmacy['postcode']}\n\n"

                    # Show metrics with numbers
                    response += f"📦 Items Dispensed: {pharmacy['items']}\n"
                    response += f"📝 Prescriptions: {pharmacy['forms']}\n"
                    response += f"🩺 CPCS: {pharmacy['cpcs']}\n"
                    response += f"💊 Pharmacy First: {pharmacy['pharmacy_first']}\n"
                    response += f"🔄 NMS: {pharmacy['nms']}\n"
                    response += f"💻 EPS Takeup: {pharmacy['eps']}\n"

                    # Delete status message and send results
                    await status_msg.delete()
                    await update.message.reply_text(response)
                else:
                    await status_msg.edit_text(f"Pharmacy with ODS code {pharmacy_id} not found.")
            except Exception as e:
                logger.error(f"Error getting direct pharmacy details: {e}")
                await status_msg.edit_text(f"Error retrieving pharmacy with code {pharmacy_id}")

            return

        # Otherwise treat as a postcode
        postcode = user_input

        # For debugging - notify admin about usage
        if os.environ.get("ADMIN_USER_ID"):
            admin_id = os.environ.get("ADMIN_USER_ID")
            try:
                # Log this search to admin if possible
                admin_context = Application.context_types.context.copy(context)
                await admin_context.bot.send_message(
                    chat_id=admin_id,
                    text=f"User {user_id} searching for '{postcode}'"
                )
            except:
                # Silently continue if admin notification fails
                pass

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
            pharmacy_ids = await asyncio.wait_for(task, timeout=30)  # Increased timeout
        except asyncio.TimeoutError:
            await status_msg.edit_text(
                "⏱️ The search is taking too long. This could be due to:\n"
                "• Heavy traffic on PharmData website\n"
                "• Connection issues\n\n"
                "Please try again in a few minutes."
            )
            return
        except Exception as e:
            logger.error(f"Error in pharmacy search: {e}")
            await status_msg.edit_text(
                "⚠️ An error occurred while searching.\n\n"
                "Please verify your postcode is correct (example: W9 1SY) and try again."
            )
            return

        if not pharmacy_ids:
            # More helpful message explaining possible reasons
            await status_msg.edit_text(
                "📭 No pharmacies found for postcode: " + postcode + "\n\n"
                "This could be because:\n"
                "• The postcode is not associated with any pharmacy\n"
                "• PharmData.co.uk might be experiencing issues\n"
                "• The website structure may have changed\n\n"
                "Try another nearby postcode or try again later."
            )
            return
            
        # Looking specifically for Boots
        await status_msg.edit_text(f"🏥 Looking for Boots pharmacy in {postcode}...")

        # Get details for each pharmacy concurrently, filter for Boots only
        results = []
        tasks = []

        # Create tasks for all pharmacy details
        for pharmacy_id in pharmacy_ids[:5]:  # Check more to increase chance of finding Boots
            tasks.append(
                asyncio.create_task(
                    asyncio.to_thread(get_pharmacy_details, pharmacy_id)
                )
            )

        # Wait for all tasks to complete
        try:
            # Process completed tasks as they finish
            boots_found = False
            for completed_task in asyncio.as_completed(tasks, timeout=30):
                pharmacy = await completed_task
                if pharmacy:
                    # Only include Boots pharmacies
                    if "Boots" in pharmacy["name"]:
                        results = [pharmacy]  # Only keep the Boots result
                        boots_found = True
                        # Update status message
                        await status_msg.edit_text(f"Found Boots pharmacy! Getting details...")
                        break  # Stop after finding Boots
                    else:
                        # Store result only if we don't have Boots yet
                        if not boots_found:
                            results.append(pharmacy)
                    # Update status message without showing numbers
                    await status_msg.edit_text(f"Searching for Boots pharmacy...")
        except asyncio.TimeoutError:
            logger.warning("Timeout getting pharmacy details")
            # Continue with any results we got
            if not results:
                await status_msg.edit_text("Timed out while retrieving pharmacy information.")
                return
        except Exception as e:
            logger.error(f"Error processing pharmacy details: {e}")
            # Continue with any results we got

        # Final filtering - ensure we only show a Boots pharmacy if available
        boots_results = [p for p in results if "Boots" in p["name"]]
        if boots_results:
            # If we have any Boots pharmacies, only show those
            results = boots_results[:1]  # Just the first Boots
        elif len(results) > 0:
            # If no Boots found, just keep first result
            results = [results[0]]

        # Update header message based on whether we found Boots
        if results and "Boots" in results[0]["name"]:
            boots_found = True
        else:
            boots_found = False

        # Format and send results
        if results:
            # Use appropriate title based on whether we found Boots
            if boots_found:
                response = "📊 Boots Pharmacy Information 📊\n"
            else:
                response = "📊 Pharmacy Information 📊\n"

            for i, pharmacy in enumerate(results):
                # Add separator line between pharmacies (except for the first one)
                if i > 0:
                    response += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

                response += f"\n🏥 Pharmacy: {pharmacy['name']}\n"

                # Add address if available
                if 'address' in pharmacy and pharmacy['address'] != "Address not found":
                    response += f"📍 Address: {pharmacy['address']}\n"

                # Add postcode
                response += f"📮 Postcode: {pharmacy['postcode']}\n\n"

                # Show metrics with numbers
                response += f"📦 Items Dispensed: {pharmacy['items']}\n"
                response += f"📝 Prescriptions: {pharmacy['forms']}\n"
                response += f"🩺 CPCS: {pharmacy['cpcs']}\n"
                response += f"💊 Pharmacy First: {pharmacy['pharmacy_first']}\n"
                response += f"🔄 NMS: {pharmacy['nms']}\n"
                response += f"💻 EPS Takeup: {pharmacy['eps']}\n"

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
