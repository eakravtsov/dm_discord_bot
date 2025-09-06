import logging
import threading
import asyncio
import os
import sys
from flask import Flask

# --- Add project root to Python path ---
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Helper and Handler Imports ---
from helpers.ConfigurationHelper import (
    setup_logging,
    load_config,
    SYSTEM_PROMPT,
    DICE_ROLLER_TOOL,
    CHARACTER_SHEET_TOOL
)
from handlers.DatabaseHandler import DatabaseHandler
from handlers.LLMHandler import LLMHandler
from handlers.DiscordHandler import DiscordHandler
from handlers.ToolHandler import ToolHandler

# --- Flask App for Health Checks ---
app = Flask(__name__)


@app.route('/')
def health_check():
    """Provides a 200 OK response for Cloud Run health checks."""
    return "OK", 200


def run_bot():
    """Sets up and runs the main bot logic."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    config = load_config()

    # --- Initialize Handlers ---
    db_handler = DatabaseHandler(
        project_id=config.get("GCP_PROJECT_ID"),
        system_prompt=SYSTEM_PROMPT,
        database_id="dnd-game-history-database"  # Corrected parameter name
    )
    if not db_handler.is_initialized():
        logging.critical("Firestore client could not be initialized in bot thread. Exiting.")
        return

    # --- Initialize Tooling ---
    tool_schemas = [DICE_ROLLER_TOOL, CHARACTER_SHEET_TOOL]
    tool_handler = ToolHandler(db_handler=db_handler)

    # --- Initialize LLM Handler with Tools ---
    try:
        llm_handler = LLMHandler(
            api_key=config.get("GOOGLE_API_KEY"),
            tool_handler=tool_handler,
            tool_schemas=tool_schemas
        )
        discord_client = DiscordHandler(llm_handler=llm_handler, game_manager=db_handler)

        loop.run_until_complete(discord_client.start(config.get("DISCORD_TOKEN")))

    except ValueError as e:
        logging.critical(f"Configuration Error in bot thread: {e}", exc_info=e)
    except Exception as e:
        logging.critical(f"An unexpected error occurred in the bot thread.", exc_info=e)


# --- Main Application Entry Point ---
setup_logging()
config = load_config()

if not all([config.get("DISCORD_TOKEN"), config.get("GOOGLE_API_KEY"), config.get("GCP_PROJECT_ID")]):
    logging.critical("One or more essential environment variables are not set. Exiting.")
else:
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    logging.info("Discord bot thread started.")

