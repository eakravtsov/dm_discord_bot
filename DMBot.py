import logging
import threading
import asyncio
from flask import Flask
from helpers.ConfigurationHelper import setup_logging, load_config, SYSTEM_PROMPT
from handlers.DatabaseHandler import DatabaseHandler
from handlers.LLMHandler import LLMHandler
from handlers.DiscordHandler import DiscordHandler

# --- Setup Logging and Flask App ---
setup_logging()
app = Flask(__name__)

@app.route("/")
def health_check():
    """Health check endpoint for Cloud Run."""
    return "OK", 200

def run_bot():
    """Initializes and runs the Discord bot in a dedicated thread."""
    # Each thread needs its own asyncio event loop.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    logging.info("Bot thread started.")
    config = load_config()

    # --- Validate Configuration ---
    if not all([config.get("DISCORD_TOKEN"), config.get("GOOGLE_API_KEY"), config.get("GCP_PROJECT_ID")]):
        logging.critical("One or more environment variables are missing. Bot thread exiting.")
        return

    # --- Initialize Services ---
    db_handler = DatabaseHandler(
        project_id=config.get("GCP_PROJECT_ID"),
        system_prompt=SYSTEM_PROMPT
    )
    if not db_handler.is_initialized():
        logging.critical("Firestore client could not be initialized. Bot thread exiting.")
        return

    # --- Run Bot ---
    try:
        llm_handler = LLMHandler(api_key=config.get("GOOGLE_API_KEY"))
        discord_client = DiscordHandler(llm_handler=llm_handler, game_manager=db_handler)
        # Use start() instead of run() for non-blocking execution in a thread.
        loop.run_until_complete(discord_client.start(config.get("DISCORD_TOKEN")))
    except Exception as e:
        logging.critical(f"An unexpected error occurred in the bot thread.", exc_info=e)
    finally:
        loop.close()
        logging.info("Bot thread event loop closed.")

# --- Start the Bot in a Background Thread ---
# This code runs when the module is imported by Gunicorn.
logging.info("Starting Discord bot in a background thread.")
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

# The 'if __name__ == "__main__":' block is removed.
# Gunicorn now serves as the entry point for the application.

