#!/usr/bin/env python
import os
import requests
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Load environment variables
load_dotenv()

def test_webhook_connection():
    """Test if the bot's webhook is correctly configured"""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logging.error("TELEGRAM_BOT_TOKEN environment variable is not set.")
        return False
    
    app_name = os.environ.get("APP_NAME")
    if not app_name:
        logging.error("APP_NAME environment variable is not set.")
        return False
    
    # Get current webhook info
    webhook_info_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
    
    try:
        response = requests.get(webhook_info_url)
        data = response.json()
        
        if response.status_code == 200 and data.get('ok'):
            webhook_info = data.get('result', {})
            logging.info(f"Current webhook URL: {webhook_info.get('url')}")
            logging.info(f"Pending updates: {webhook_info.get('pending_update_count')}")
            
            if webhook_info.get('url'):
                expected_url = f"https://{app_name}.herokuapp.com/{bot_token}"
                if webhook_info.get('url') == expected_url:
                    logging.info("✅ Webhook URL is correctly configured.")
                else:
                    logging.warning(f"❌ Webhook URL mismatch. Expected: {expected_url}")
            else:
                logging.warning("❌ No webhook URL is currently set.")
                
            # Check for any errors
            if webhook_info.get('last_error_date'):
                last_error_time = webhook_info.get('last_error_date')
                last_error_message = webhook_info.get('last_error_message')
                logging.error(f"❌ Last webhook error: {last_error_message} (at timestamp {last_error_time})")
            else:
                logging.info("✅ No webhook errors reported.")
                
            return True
        else:
            logging.error(f"Failed to get webhook info: {data.get('description')}")
            return False
            
    except Exception as e:
        logging.error(f"Error testing webhook: {e}")
        return False
        
def delete_and_set_webhook():
    """Delete and re-set the webhook"""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logging.error("TELEGRAM_BOT_TOKEN environment variable is not set.")
        return False
    
    app_name = os.environ.get("APP_NAME")
    if not app_name:
        logging.error("APP_NAME environment variable is not set.")
        return False
    
    # First delete the current webhook
    delete_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
    try:
        response = requests.get(delete_url)
        data = response.json()
        
        if response.status_code == 200 and data.get('ok'):
            logging.info("Successfully deleted current webhook.")
        else:
            logging.error(f"Failed to delete webhook: {data.get('description')}")
            return False
    except Exception as e:
        logging.error(f"Error deleting webhook: {e}")
        return False
    
    # Now set the new webhook
    webhook_url = f"https://{app_name}.herokuapp.com/{bot_token}"
    set_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    params = {
        'url': webhook_url,
        'allowed_updates': ['message', 'callback_query']
    }
    
    try:
        response = requests.post(set_url, json=params)
        data = response.json()
        
        if response.status_code == 200 and data.get('ok'):
            logging.info(f"Successfully set new webhook to {webhook_url}")
            return True
        else:
            logging.error(f"Failed to set webhook: {data.get('description')}")
            return False
    except Exception as e:
        logging.error(f"Error setting webhook: {e}")
        return False

if __name__ == "__main__":
    print("Testing Telegram webhook configuration...")
    test_webhook_connection()
    
    answer = input("Do you want to delete and re-set the webhook? (y/n): ")
    if answer.lower() == 'y':
        delete_and_set_webhook()
        test_webhook_connection()
