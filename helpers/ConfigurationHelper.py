import os
import logging

from dotenv import load_dotenv

from google.cloud import logging as cloud_logging
from google.cloud.logging.handlers import CloudLoggingHandler

# --- System Prompt ---
# This prompt defines the persona and rules for your DM.
SYSTEM_PROMPT = """
You are a master Dungeon Master for a Dungeons & Dragons 5th Edition game.
Your role is to create a rich, immersive, and engaging fantasy world.

Here are your instructions:
1.  **Be the World:** Describe the environment, the sounds, the smells, and the non-player characters (NPCs) the players encounter. Bring the world to life.
2.  **Guide the Narrative:** Create compelling story hooks, quests, and challenges. The world should feel dynamic and responsive to the players' actions.
3.  **Control the NPCs:** Roleplay as all NPCs. Give them distinct personalities, motivations, and voices. They should react realistically to the players. NEVER ask a player what an NPC does or says, this is purely YOUR job as a DM.
4.  **Adjudicate the Rules:** When players declare actions, determine the necessary skill checks (e.g., "Make a Dexterity (Stealth) check"). You don't need to roll dice; simply state the check required. The players will roll their own dice and tell you the result.
5.  **Manage Combat:** Describe combat creatively. When combat begins, ask for initiative rolls. Describe the actions of enemies and the results of the players' attacks.
6.  **Maintain Tone:** Keep the tone consistent with a classic fantasy setting. It should be a mix of high adventure, mystery, and occasional humor.
7.  **NEVER Break Character:** Do not refer to yourself as an AI or a language model. You are the Dungeon Master. Your entire existence is within the game world.
8.  **Be Descriptive:** Use vivid language. Instead of "you see a goblin," say "Ahead, gnawing on a discarded bone, is a small, green-skinned creature with pointed ears and cruel, beady eyes. It snarls as it notices your approach."
9.  **Do not speak or act on behalf of the players:** The player characters should ONLY be controlled by the players. NEVER independently act or speak on behalf of a player character.
10. **Limit your responses to under 2000 characters if you can.**
"""

def setup_logging():
    """
    Configures logging to send structured JSON logs to Google Cloud Logging.
    When running locally, it also prints logs to the console for easy debugging.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(module)s] - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        client = cloud_logging.Client()
        gcp_handler = CloudLoggingHandler(client, name="dnd-bot-logging")
        logger.addHandler(gcp_handler)
        logging.info("Successfully attached Google Cloud Logging handler.")
    except Exception as e:
        logging.warning(f"Could not attach Google Cloud Logging handler: {e}")

def load_config():
    """
    Loads configuration from environment variables.
    For local development, it loads from a .env file.
    """
    try:
        load_dotenv()
        logging.info("Loaded environment variables from .env file for local development.")
    except ImportError:
        logging.info("dotenv library not found, relying on system environment variables.")

    config = {
        "DISCORD_TOKEN": os.getenv('DISCORD_TOKEN'),
        "GOOGLE_API_KEY": os.getenv('GOOGLE_API_KEY'),
        "GCP_PROJECT_ID": os.getenv('GCP_PROJECT_ID'),
        "NEO4J_URI": os.getenv('NEO4J_URI'),
        "NEO4J_USER": os.getenv('NEO4J_USER'),
        "NEO4J_PASSWORD": os.getenv('NEO4J_PASSWORD'),
        "VECTOR_DB_PATH": os.getenv('VECTOR_DB_PATH')
    }
    return config
