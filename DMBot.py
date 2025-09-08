# --- DMBot.py (Refactored for Compute Engine) ---
import logging
import asyncio
from helpers.ConfigurationHelper import setup_logging, load_config, SYSTEM_PROMPT
from handlers.DatabaseHandler import DatabaseHandler
from handlers.LLMHandler import LLMHandler
from handlers.DiscordHandler import DiscordHandler

# --- Setup Logging ---
setup_logging()

def main():
    """
    Initializes and runs the Discord bot application.
    """
    logging.info("Starting Dungeon Master Bot...")

    # --- Load and Validate Configuration ---
    config = load_config()
    if not all([config.get("DISCORD_TOKEN"), config.get("GOOGLE_API_KEY"), config.get("GCP_PROJECT_ID")]):
        logging.critical("One or more critical environment variables (DISCORD_TOKEN, GOOGLE_API_KEY, GCP_PROJECT_ID) are missing. Shutting down.")
        return  # Exit the application

    logging.info("Configuration loaded successfully.")
    # --- Initialize Handlers ---
    try:
        # Database handler is critical, initialize it first.
        db_handler = DatabaseHandler(
            project_id=config.get("GCP_PROJECT_ID"),
            system_prompt=SYSTEM_PROMPT
        )
        if not db_handler.is_initialized():
            logging.critical("Firestore client could not be initialized. Shutting down.")
            return # Exit the application

        # Initialize the LLM handler.
        llm_handler = LLMHandler(api_key=config.get("GOOGLE_API_KEY"))

        # Connect the LLM handler to the database handler for summarization.
        db_handler.set_llm_handler(llm_handler)

        # Initialize the Discord client, passing it the other handlers.
        discord_client = DiscordHandler(llm_handler=llm_handler, game_manager=db_handler)

    except Exception as e:
        logging.critical(f"A fatal error occurred during service initialization.", exc_info=e)
        return # Exit the application

    # --- Run the Bot ---
    try:
        logging.info("All services initialized. Starting the Discord client.")
        # This is a blocking call that runs the bot's event loop.
        # It will run indefinitely until the bot is disconnected or an error occurs.
        asyncio.run(discord_client.start(config.get("DISCORD_TOKEN")))
    except Exception as e:
        logging.critical(f"An unexpected error occurred while running the bot.", exc_info=e)
    finally:
        logging.info("Bot has been shut down.")

if __name__ == "__main__":
    main()