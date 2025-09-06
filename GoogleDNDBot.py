import os
import discord
import google.generativeai as genai
from google.cloud import firestore
import logging
from google.cloud.logging.handlers import CloudLoggingHandler

# --- Setup Structured Logging ---
# This configures logging to send structured JSON logs to Google Cloud Logging.
# When running locally, it also prints logs to the console.
def setup_logging():
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO) # Set the default level

    # Remove any existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    # Add a stream handler to see logs in the console
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add the Google Cloud Logging handler
    try:
        # The client will be implicitly created using the environment's credentials.
        gcp_handler = CloudLoggingHandler(name="dnd-bot-logging")
        logger.addHandler(gcp_handler)
        logging.info("Successfully attached Google Cloud Logging handler.")
    except Exception as e:
        logging.warning(f"Could not attach Google Cloud Logging handler: {e}")

# --- System Prompt ---
SYSTEM_PROMPT = """
You are a master Dungeon Master for a Dungeons & Dragons 5th Edition game.
Your role is to create a rich, immersive, and engaging fantasy world.
(Instructions remain the same...)
"""


class GameManager:
    """Manages game state and conversation history using Firestore."""
    def __init__(self, system_prompt, firestore_db):
        if not firestore_db:
            raise ValueError("Firestore database client is not initialized.")
        self.system_prompt = system_prompt
        self.db = firestore_db
        self.collection_ref = self.db.collection('dnd_sessions')

    def _get_initial_history(self):
        return [{'role': 'user', 'parts': [self.system_prompt]},
                {'role': 'model', 'parts': ["Understood. The world is ready. I will await the adventurers."]}
               ]

    async def _ensure_user_document_exists(self, user_id):
        user_doc_ref = self.collection_ref.document(str(user_id))
        doc = await user_doc_ref.get()
        if not doc.exists:
            logging.info(f"First interaction from user {user_id}. Creating new game document.")
            initial_history = self._get_initial_history()
            await user_doc_ref.set({'history': initial_history})
        return user_doc_ref

    async def get_history(self, user_id):
        user_doc_ref = await self._ensure_user_document_exists(user_id)
        doc = await user_doc_ref.get()
        return doc.to_dict().get('history')

    async def add_message(self, user_id, role, message):
        user_doc_ref = await self._ensure_user_document_exists(user_id)
        update_data = {'history': firestore.ArrayUnion([{'role': role, 'parts': [message]}])}
        await user_doc_ref.update(update_data)
        logging.info(f"Added message for user {user_id}.")

    async def reset_history(self, user_id):
        user_doc_ref = self.collection_ref.document(str(user_id))
        initial_history = self._get_initial_history()
        await user_doc_ref.set({'history': initial_history})
        logging.info(f"History reset for user {user_id}.")


class LLM:
    """Handles interactions with the Google Gemini model."""
    def __init__(self, api_key):
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash',
            generation_config=genai.GenerationConfig(temperature=0.8, top_p=0.95, top_k=40))

    async def generate_response(self, history):
        try:
            logging.info("Generating response from LLM...")
            chat_session = self.model.start_chat(history=history)
            response = await chat_session.send_message_async(history[-1]['parts'][0])
            logging.info("Response generated successfully.")
            return response.text
        except Exception as e:
            logging.error("An error occurred while generating the LLM response.", exc_info=e)
            return "The world seems to shimmer and fade for a moment. I... I lost my train of thought. Can you repeat that?"


class DnDDiscordBot(discord.Client):
    """The main Discord bot class that ties everything together."""
    def __init__(self, llm_handler, game_manager, **options):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents, **options)
        self.llm = llm_handler
        self.game_manager = game_manager
        logging.info("Discord Bot initialized.")

    async def on_ready(self):
        logging.info(f'Logged in as {self.user.name} ({self.user.id})')
        logging.info('The DM is ready to begin the adventure!')

    async def on_message(self, message):
        if message.author == self.user:
            return
        if not self.user.mentioned_in(message) and not message.content.startswith('!'):
            return

        user_id = str(message.author.id)
        user_message = message.content.replace(f'<@{self.user.id}>', '').strip()

        # Added a log to track all interactions, including commands.
        logging.info(f"Received message from user '{message.author.name}' ({user_id})", extra={'json_fields': {'discord_user': message.author.name, 'user_id': user_id, 'message_content': user_message}})

        if user_message.lower() == '!newgame':
            await self.game_manager.reset_history(user_id)
            await message.channel.send("The mists clear, and a new adventure begins... (Your story has been reset). What do you do?")
            return

        async with message.channel.typing():
            await self.game_manager.add_message(user_id, 'user', f"{message.author.name} says: {user_message}")
            history = await self.game_manager.get_history(user_id)
            dm_response = await self.llm.generate_response(history)
            await self.game_manager.add_message(user_id, 'model', dm_response)
            await message.channel.send(dm_response)

def load_config():
    """Loads configuration from environment variables."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logging.info("Loaded environment variables from .env file for local development.")
    except ImportError:
        logging.info("dotenv library not found, relying on system environment variables for production.")
    return {
        "DISCORD_TOKEN": os.getenv('DISCORD_TOKEN'),
        "GOOGLE_API_KEY": os.getenv('GOOGLE_API_KEY'),
        "GCP_PROJECT_ID": os.getenv('GCP_PROJECT_ID')
    }

def initialize_firestore(project_id):
    """Initializes and returns a Firestore AsyncClient."""
    if not project_id:
        logging.error("GCP_PROJECT_ID environment variable not set.")
        return None
    try:
        db = firestore.AsyncClient(project=project_id, database="dnd-game-history-database")
        logging.info("Firestore initialized successfully for database 'dnd-game-history-database'.")
        return db
    except Exception as e:
        logging.error("Error initializing Firestore.", exc_info=e)
        return None

def main():
    """Main function to setup logging, load config, initialize services, and run the bot."""
    setup_logging() # Setup logging first
    config = load_config()

    if not config.get("DISCORD_TOKEN"):
        logging.critical("DISCORD_TOKEN environment variable not set. Exiting.")
        return

    db = initialize_firestore(config.get("GCP_PROJECT_ID"))
    if not db:
        logging.critical("Firestore client could not be initialized. Exiting.")
        return

    try:
        game_manager = GameManager(system_prompt=SYSTEM_PROMPT, firestore_db=db)
        llm_handler = LLM(api_key=config.get("GOOGLE_API_KEY"))
        bot = DnDDiscordBot(llm_handler=llm_handler, game_manager=game_manager)
        bot.run(config.get("DISCORD_TOKEN"))
    except ValueError as e:
        logging.critical(f"Configuration Error: {e}", exc_info=e)
    except Exception as e:
        logging.critical(f"An unexpected error occurred at the application's root.", exc_info=e)

if __name__ == '__main__':
    main()

