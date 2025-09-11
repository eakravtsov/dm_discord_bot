import logging
import asyncio
from helpers.ConfigurationHelper import setup_logging, load_config, SYSTEM_PROMPT
from handlers.DatabaseHandler import DatabaseHandler
from handlers.LLMHandler import LLMHandler
from handlers.DiscordHandler import DiscordHandler
from handlers.GraphHandler import GraphHandler
from handlers.VectorStoreHandler import VectorStoreHandler

setup_logging()


def main():
    """Initializes and runs the Discord bot application."""
    logging.info("Starting Dungeon Master Bot...")

    config = load_config()
    required_vars = [
        "DISCORD_TOKEN", "GOOGLE_API_KEY", "GCP_PROJECT_ID",
        "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "VECTOR_DB_PATH"
    ]
    if not all(config.get(var) for var in required_vars):
        logging.critical("One or more critical environment variables are missing. Shutting down.")
        return

    logging.info("Configuration loaded successfully.")

    graph_handler = None  # Initialize to None for the finally block
    try:
        # --- Initialize Handlers ---
        db_handler = DatabaseHandler(project_id=config["GCP_PROJECT_ID"], system_prompt=SYSTEM_PROMPT)
        if not db_handler.is_initialized():
            logging.critical("Firestore client could not be initialized. Shutting down.")
            return

        llm_handler = LLMHandler(api_key=config["GOOGLE_API_KEY"])

        graph_handler = GraphHandler(
            uri=config["NEO4J_URI"],
            user=config["NEO4J_USER"],
            password=config["NEO4J_PASSWORD"]
        )

        vector_store_handler = VectorStoreHandler(
            embedding_model=llm_handler,
            db_path=config["VECTOR_DB_PATH"]
        )

        discord_client = DiscordHandler(
            llm_handler=llm_handler,
            game_manager=db_handler,
            graph_handler=graph_handler,
            vector_store_handler=vector_store_handler
        )

        db_handler.set_handlers(llm_handler, graph_handler, vector_store_handler)

        # --- Run the Bot ---
        logging.info("All services initialized. Starting the Discord client.")
        asyncio.run(discord_client.start(config["DISCORD_TOKEN"]))

    except Exception as e:
        logging.critical("A fatal error occurred during service initialization or runtime.", exc_info=e)
    finally:
        if graph_handler:
            asyncio.run(graph_handler.close())
        logging.info("Bot has been shut down.")


if __name__ == "__main__":
    main()
