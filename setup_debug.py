#!/usr/bin/env python
import os
import logging
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Configure basic logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def test_chrome_setup():
    """Test if Chrome is available and can be initialized"""
    logger.info("Testing Chrome setup...")
    
    # Check Chrome binary paths
    chrome_paths = [
        '/app/.apt/usr/bin/google-chrome',
        '/app/.chrome-for-testing/chrome-linux64/chrome',
        '/usr/bin/google-chrome',
    ]
    
    chrome_bin = None
    for path in chrome_paths:
        if os.path.exists(path):
            logger.info(f"Chrome binary found at: {path}")
            chrome_bin = path
            break
    
    if not chrome_bin:
        logger.error("No Chrome binary found at any of the expected paths")
        return False
    
    # Try to initialize Chrome
    options = Options()
    options.binary_location = chrome_bin
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    try:
        logger.info("Initializing Chrome with options:")
        logger.info(f"  Binary: {options.binary_location}")
        logger.info(f"  Arguments: {options.arguments}")
        
        driver = webdriver.Chrome(options=options)
        logger.info("Chrome initialization successful")
        driver.quit()
        return True
    except Exception as e:
        logger.error(f"Chrome initialization failed: {e}")
        return False

def show_environment():
    """Show environment variables and system info"""
    logger.info("Environment information:")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    
    # Check critical environment variables
    env_vars = ['TELEGRAM_BOT_TOKEN', 'APP_NAME', 'PORT', 'GOOGLE_CHROME_BIN']
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            # Obscure token for security
            if var == 'TELEGRAM_BOT_TOKEN':
                logger.info(f"{var}: {value[:4]}...{value[-4:]}")
            else:
                logger.info(f"{var}: {value}")
        else:
            logger.warning(f"{var} is not set")
    
    return True

if __name__ == "__main__":
    logger.info("Starting setup debug...")
    show_environment()
    test_chrome_setup()
    logger.info("Setup debug complete.")
