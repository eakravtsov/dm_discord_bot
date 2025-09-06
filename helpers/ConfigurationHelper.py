import os
import logging

from google.cloud import logging as cloud_logging

# --- System Prompt ---
SYSTEM_PROMPT = """
You are a master Dungeon Master for a Dungeons & Dragons 5th Edition game.
Your role is to create a rich, immersive, and engaging fantasy world.

Here are your instructions:
1.  **Be the World:** Describe the environment, the sounds, the smells, and the non-player characters (NPCs) the players encounter. Bring the world to life.
2.  **Use Your Tools:** When you need to determine a random outcome or access information about a character, you MUST use the tools provided.
    - To roll dice for skill checks, attacks, or damage, call the `roll_dice` function. Announce the roll and its result to the player. For example: "The goblin swings its scimitar! (Rolling 1d20+2)... The roll is 14. That's a hit!"
    - To get information about a character (PC or NPC), like their stats, abilities, or inventory, call the `get_character_sheet` function. Do not invent stats for characters if a sheet might exist.
3.  **Control the NPCs:** Roleplay as all NPCs. Give them distinct personalities, motivations, and voices. They should react realistically to the players.
4.  **Manage Combat:** Describe combat creatively. When combat begins, ask for initiative rolls. Describe the actions of enemies and the results of the players' attacks based on your dice rolls.
5.  **Maintain Tone:** Keep the tone consistent with a classic fantasy setting. It should be a mix of high adventure, mystery, and occasional humor.
6.  **NEVER Break Character:** Do not refer to yourself as an AI or a language model. You are the Dungeon Master. Your entire existence is within the game world.
"""

# --- Tool Schemas for Function Calling ---
# FIX: The 'type' fields have been changed to uppercase (e.g., "OBJECT", "STRING")
# to match the format expected by the Google AI library.
DICE_ROLLER_TOOL = {
    "name": "roll_dice",
    "description": "Rolls dice for skill checks, attacks, or damage. Use this whenever the DM needs to determine a random outcome based on dice.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "dice_expression": {
                "type": "STRING",
                "description": "The dice expression to roll, e.g., '1d20+5', '2d6', '3d8-1'."
            }
        },
        "required": ["dice_expression"]
    }
}

CHARACTER_SHEET_TOOL = {
    "name": "get_character_sheet",
    "description": "Retrieves the character sheet for a specific player character (PC) or non-player character (NPC) to get their stats, abilities, or inventory.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "character_name": {
                "type": "STRING",
                "description": "The name of the character to look up."
            }
        },
        "required": ["character_name"]
    }
}

# --- JSON Schema for Character Sheets ---
# FIX: The 'type' fields have been changed to uppercase.
CHARACTER_SHEET_JSON_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": {"type": "STRING"},
        "class": {"type": "STRING"},
        "race": {"type": "STRING"},
        "level": {"type": "INTEGER"},
        "alignment": {"type": "STRING"},
        "background": {"type": "STRING"},
        "stats": {
            "type": "OBJECT",
            "properties": {
                "strength": {"type": "INTEGER"},
                "dexterity": {"type": "INTEGER"},
                "constitution": {"type": "INTEGER"},
                "intelligence": {"type": "INTEGER"},
                "wisdom": {"type": "INTEGER"},
                "charisma": {"type": "INTEGER"}
            }
        },
        "hp": {
            "type": "OBJECT",
            "properties": {
                "max": {"type": "INTEGER"},
                "current": {"type": "INTEGER"}
            }
        },
        "ac": {"type": "INTEGER"},
        "speed": {"type": "STRING"},
        "skills": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        },
        "saving_throws": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        },
        "features": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        },
        "inventory": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        },
        "backstory": {"type": "STRING"}
    },
    "required": ["name", "class", "race", "level", "stats", "hp", "ac", "inventory", "backstory"]
}


def setup_logging():
    # Set up basic configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(module)s] - %(message)s',
    )
    # Set up the Google Cloud Logging client
    try:

        client = cloud_logging.Client()
        handler = client.get_default_handler()
        logging.getLogger().addHandler(handler)
        logging.info("Successfully attached Google Cloud Logging handler.")
    except ImportError:
        logging.warning("google-cloud-logging not found. Logging to console only.")
    except Exception as e:
        logging.warning(f"Could not attach Google Cloud Logging handler: {e}")

    # For local development, try to load .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logging.info("Loaded environment variables from .env file for local development.")
    except ImportError:
        logging.info("dotenv library not found, relying on system environment variables.")


def load_config():
    """Loads configuration from environment variables."""
    return {
        "DISCORD_TOKEN": os.getenv('DISCORD_TOKEN'),
        "GOOGLE_API_KEY": os.getenv('GOOGLE_API_KEY'),
        "GCP_PROJECT_ID": os.getenv('GCP_PROJECT_ID')
    }

