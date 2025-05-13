#!/usr/bin/env python
import os
import logging
import asyncio
from pharmacy_data import telegram_bot_main

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

if __name__ == "__main__":
    try:
        logging.info("Starting Telegram bot from run.py...")
        # This is the correct way to run async code in the entry point
        asyncio.run(telegram_bot_main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
    except Exception as e:
        logging.error(f"Unexpected error in run.py: {e}")
