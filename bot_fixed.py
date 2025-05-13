#!/usr/bin/env python
import os
import logging
import sys
import asyncio
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded environment variables from .env file")
except ImportError:
    print("dotenv not available, using system environment variables")

# Configure basic logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Apply nest_asyncio to allow nested async loops
nest_asyncio.apply()

# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the /start command is issued"""
    try:
        logger.info(f"User {update.effective_user.id} started the bot")
        await update.message.reply_text('سلام عزیزم! من ربات اطلاعات داروخانه هستم. لطفاً یک کد پستی بریتانیا وارد کن')
    except Exception as e:
        logger.error(f"Error in start command: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message when the /help command is issued"""
    try:
        await update.message.reply_text('برای استفاده از ربات فقط کافیست یک کد پستی بریتانیا وارد کنید.')
    except Exception as e:
        logger.error(f"Error in help command: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages"""
    try:
        logger.info(f"Received message from user {update.effective_user.id}: {update.message.text}")
        await update.message.reply_text(f"شما وارد کردید: {update.message.text}\n\nاین نسخه آزمایشی برای بررسی اتصال است. لطفاً صبر کنید تا نسخه کامل به زودی فعال شود.")
    except Exception as e:
        logger.error(f"Error handling message: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates"""
    logger.error(f"Update {update} caused error: {context.error}")
    
    # Send a message to the user if possible
    if update and isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("مشکلی رخ داد. لطفاً بعداً تلاش کنید.")

def main():
    """Start the bot"""
    # Get token from environment variable
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("No bot token found. Set TELEGRAM_BOT_TOKEN environment variable.")
        return

    # Create the Application
    application = Application.builder().token(bot_token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)

    # Start the Bot
    port = int(os.environ.get('PORT', 5000))
    app_name = os.environ.get('APP_NAME')
    
    logger.info(f"Starting bot with TOKEN={bot_token[:4]}...{bot_token[-4:]}")
    
    if app_name:  # Running on Heroku
        # Use webhook mode
        webhook_url = f"https://{app_name}.herokuapp.com/{bot_token}"
        logger.info(f"Starting webhook on {app_name}.herokuapp.com on port {port}")
        logger.info(f"Webhook URL: {webhook_url}")
        
        # Run the bot with webhook
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=bot_token,
            webhook_url=webhook_url,
        )
    else:  # Running locally
        # Use polling mode
        logger.info("Starting polling")
        application.run_polling()

if __name__ == '__main__':
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Starting bot...")
    main()
    logger.info("Bot stopped.")
