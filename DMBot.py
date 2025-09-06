import logging
from helpers.ConfigurationHelper import setup_logging, load_config, SYSTEM_PROMPT
from handlers.DatabaseHandler import DatabaseHandler
from handlers.LLMHandler import LLMHandler
from handlers.DiscordHandler import DiscordHandler

def main():
    """Main function to setup logging, load config, initialize services, and run the bot."""
    setup_logging()
    config = load_config()

    # --- Validate Configuration ---
    if not config.get("DISCORD_TOKEN"):
        logging.critical("DISCORD_TOKEN environment variable not set. Exiting.")
        return
    if not config.get("GOOGLE_API_KEY"):
        logging.critical("GOOGLE_API_KEY environment variable not set. Exiting.")
        return
    if not config.get("GCP_PROJECT_ID"):
        logging.critical("GCP_PROJECT_ID environment variable not set. Exiting.")
        return

    # --- Initialize Services ---
    # The initialize_firestore function is now part of the DatabaseHandler class constructor
    db_handler = DatabaseHandler(
        project_id=config.get("GCP_PROJECT_ID"),
        system_prompt=SYSTEM_PROMPT
    )
    if not db_handler.is_initialized():
        logging.critical("Firestore client could not be initialized. Exiting.")
        return

    # --- Run Bot ---
    try:
        llm_handler = LLMHandler(api_key=config.get("GOOGLE_API_KEY"))
        discord_client = DiscordHandler(llm_handler=llm_handler, game_manager=db_handler)
        discord_client.run(config.get("DISCORD_TOKEN"))
    except ValueError as e:
        logging.critical(f"Configuration Error: {e}", exc_info=e)
    except Exception as e:
        logging.critical(f"An unexpected error occurred at the application's root.", exc_info=e)

if __name__ == '__main__':
    main()
