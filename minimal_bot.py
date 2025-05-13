#!/usr/bin/env python
import os
import logging
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Basic command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    logger.info(f"User {update.effective_user.id} started the bot")
    await update.message.reply_text('Hi! I am a test bot. Type /help to see available commands.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text('Available commands:\n/start - Start the bot\n/help - Show this help message')

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    logger.info(f"Received message: {update.message.text}")
    await update.message.reply_text(f"You said: {update.message.text}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by Updates."""
    logger.error(f"Update {update} caused error: {context.error}")

def main() -> None:
    """Start the bot."""
    # Get the token from env
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No TELEGRAM_BOT_TOKEN provided")
        return

    # Create the Application
    app = Application.builder().token(token).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.add_error_handler(error_handler)

    # Get port and app name from environment (for Heroku)
    port = int(os.environ.get("PORT", "8443"))
    app_name = os.environ.get("APP_NAME")

    # Check if running on Heroku or locally
    if app_name:
        # Use webhook when on Heroku
        logger.info(f"Starting webhook on port {port}")
        webhook_url = f"https://{app_name}.herokuapp.com/{token}"
        logger.info(f"Setting webhook URL: {webhook_url}")
        
        # Start the webhook
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=token,
            webhook_url=webhook_url,
        )
    else:
        # Use polling locally
        logger.info("Starting polling")
        app.run_polling()

if __name__ == "__main__":
    logger.info(f"Python {sys.version}")
    logger.info("Starting minimal bot")
    
    try:
        main()
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
