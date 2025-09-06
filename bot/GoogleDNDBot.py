import os
import discord
import google.generativeai as genai
from google.cloud import firestore

# --- Configuration ---
# These are loaded from the environment variables in Google Cloud Run or a .env file
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GCP_PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')

# --- Firestore Initialization ---
# The AsyncClient is suitable for use with discord.py's async environment.
try:
    db = firestore.AsyncClient(project=GCP_PROJECT_ID)
    print("Firestore initialized successfully.")
except Exception as e:
    print(f"Error initializing Firestore: {e}. Ensure GOOGLE_CLOUD_PROJECT is set and authentication is configured.")
    db = None

# --- System Prompt ---
# This prompt defines the persona and rules for your DM.
# A detailed prompt is key to a good D&D experience.
SYSTEM_PROMPT = """
You are a master Dungeon Master for a Dungeons & Dragons 5th Edition game.
Your role is to create a rich, immersive, and engaging fantasy world.

Here are your instructions:
1.  **Be the World:** Describe the environment, the sounds, the smells, and the non-player characters (NPCs) the players encounter. Bring the world to life.
2.  **Guide the Narrative:** Create compelling story hooks, quests, and challenges. The world should feel dynamic and responsive to the players' actions.
3.  **Control the NPCs:** Roleplay as all NPCs. Give them distinct personalities, motivations, and voices. They should react realistically to the players.
4.  **Adjudicate the Rules:** When players declare actions, determine the necessary skill checks (e.g., "Make a Dexterity (Stealth) check"). You don't need to roll dice; simply state the check required. The players will roll their own dice and tell you the result.
5.  **Manage Combat:** Describe combat creatively. When combat begins, ask for initiative rolls. Describe the actions of enemies and the results of the players' attacks.
6.  **Maintain Tone:** Keep the tone consistent with a classic fantasy setting. It should be a mix of high adventure, mystery, and occasional humor.
7.  **NEVER Break Character:** Do not refer to yourself as an AI or a language model. You are the Dungeon Master. Your entire existence is within the game world.
8.  **Be Descriptive:** Use vivid language. Instead of "you see a goblin," say "Ahead, gnawing on a discarded bone, is a small, green-skinned creature with pointed ears and cruel, beady eyes. It snarls as it notices your approach."
9.  **Players can override you with the CORRECTION: syntax.* You MUST comply with the player's CORRECTION if they issue a CORRECTION in relation to the game, unless it conflicts with the Terms of Service (illegal activity, etc.)
"""

class GameManager:
    """Manages game state and conversation history using Firestore."""
    def __init__(self, system_prompt, firestore_db):
        """Initializes the game manager with a system prompt and Firestore client."""
        if not firestore_db:
            raise ValueError("Firestore database client is not initialized.")
        self.system_prompt = system_prompt
        self.db = firestore_db
        self.collection_ref = self.db.collection('dnd_sessions')

    def _get_initial_history(self):
        """Returns the initial history for a new game."""
        return [{'role': 'user', 'parts': [self.system_prompt]},
                {'role': 'model', 'parts': ["Understood. The world is ready. I will await the adventurers."]}
               ]

    async def get_history(self, user_id):
        """
        Retrieves the conversation history for a specific user from Firestore.
        If no history exists, it creates a new one.
        """
        user_doc_ref = self.collection_ref.document(str(user_id))
        doc = await user_doc_ref.get()
        if not doc.exists:
            print(f"No history found for user {user_id}. Creating new game.")
            initial_history = self._get_initial_history()
            await user_doc_ref.set({'history': initial_history})
            return initial_history
        return doc.to_dict().get('history', self._get_initial_history())

    async def add_message(self, user_id, role, message):
        """Adds a message to a user's conversation history in Firestore."""
        user_doc_ref = self.collection_ref.document(str(user_id))
        update_data = {'history': firestore.ArrayUnion([{'role': role, 'parts': [message]}])}
        await user_doc_ref.update(update_data)
        print(f"Added message for user {user_id}.")

    async def reset_history(self, user_id):
        """Resets a user's history in Firestore to the initial state."""
        user_doc_ref = self.collection_ref.document(str(user_id))
        initial_history = self._get_initial_history()
        await user_doc_ref.set({'history': initial_history})
        print(f"History reset for user {user_id}.")


class LLM:
    """Handles interactions with the Google Gemini model."""
    def __init__(self, api_key):
        """Configures the generative AI model."""
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set. Please check your environment variables.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config=genai.GenerationConfig(
                temperature=0.8, top_p=0.95, top_k=40
            )
        )

    async def generate_response(self, history):
        """Generates a response from the LLM based on conversation history."""
        try:
            print("Generating response from LLM...")
            chat_session = self.model.start_chat(history=history)
            user_prompt = history[-1]['parts'][0]
            response = await chat_session.send_message_async(user_prompt)
            print("Response generated successfully.")
            return response.text
        except Exception as e:
            print(f"An error occurred while generating the LLM response: {e}")
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
        print("Discord Bot initialized.")

    async def on_ready(self):
        print(f'Logged in as {self.user.name} ({self.user.id})')
        print('The DM is ready to begin the adventure!')
        print('-----------------------------------------')

    async def on_message(self, message):
        if message.author == self.user:
            return
        if not self.user.mentioned_in(message) and not message.content.startswith('!'):
            return

        user_id = str(message.author.id)
        user_message = message.content.replace(f'<@{self.user.id}>', '').strip()

        if user_message.lower() == '!newgame':
            await self.game_manager.reset_history(user_id)
            await message.channel.send("The mists clear, and a new adventure begins for you... (Your story has been reset). What do you do?")
            return

        print(f"Received message from {message.author.name} ({user_id}): '{user_message}'")
        await self.game_manager.add_message(user_id, 'user', f"{message.author.name} says: {user_message}")

        async with message.channel.typing():
            history = await self.game_manager.get_history(user_id)
            dm_response = await self.llm.generate_response(history)
            await self.game_manager.add_message(user_id, 'model', dm_response)
            await message.channel.send(dm_response)

def main():
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set.")
        return
    if not db:
        print("Error: Firestore client could not be initialized. Exiting.")
        return

    try:
        game_manager = GameManager(system_prompt=SYSTEM_PROMPT, firestore_db=db)
        llm_handler = LLM(api_key=GOOGLE_API_KEY)
        bot = DnDDiscordBot(llm_handler=llm_handler, game_manager=game_manager)
        bot.run(DISCORD_TOKEN)
    except ValueError as e:
        print(f"Configuration Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == '__main__':
    try:
        from dotenv import load_dotenv
        load_dotenv()
        DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
        GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
        GCP_PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')
    except ImportError:
        print("dotenv library not found, relying on system environment variables.")

    main()




class GameManager:
    """Manages the game state and conversation history."""

    def __init__(self, system_prompt):
        """Initializes the game with a system prompt and an empty history."""
        self.system_prompt = system_prompt
        self.history = []
        self.reset_history()

    def add_message(self, role, message):
        """Adds a message to the conversation history."""
        self.history.append({'role': role, 'parts': [message]})

    def get_history(self):
        """Returns the full conversation history."""
        return self.history

    def reset_history(self):
        """Clears the history and re-adds the system prompt to start a new game."""
        self.history = [{'role': 'user', 'parts': [self.system_prompt]},
                        {'role': 'model', 'parts': ["Understood. The world is ready. I will await the adventurers."]}
                        ]
        print("A new game has begun. History has been reset.")


class LLM:
    """Handles interactions with the Google Gemini model."""

    def __init__(self, api_key):
        """Configures the generative AI model."""
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set. Please check your environment variables.")
        genai.configure(api_key=api_key)
        # Model configuration for safety and generation settings.
        self.model = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config=genai.GenerationConfig(
                temperature=0.8,
                top_p=0.95,
                top_k=40
            )
        )

    async def generate_response(self, history):
        """
        Generates a response from the LLM based on conversation history.

        Args:
            history (list): The conversation history.

        Returns:
            str: The generated text response from the model.
        """
        try:
            print("Generating response from LLM...")
            chat_session = self.model.start_chat(history=history)
            # The last message is the user's prompt
            user_prompt = history[-1]['parts'][0]
            response = await chat_session.send_message_async(user_prompt)
            print("Response generated successfully.")
            return response.text
        except Exception as e:
            print(f"An error occurred while generating the LLM response: {e}")
            return "The world seems to shimmer and fade for a moment. I... I lost my train of thought. Can you repeat that?"


class DnDDiscordBot(discord.Client):
    """The main Discord bot class that ties everything together."""

    def __init__(self, llm_handler, game_manager, **options):
        """
        Initializes the bot with intents and handlers.

        Args:
            llm_handler (LLM): The handler for the language model.
            game_manager (GameManager): The manager for the game state.
        """
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents, **options)

        self.llm = llm_handler
        self.game_manager = game_manager
        print("Discord Bot initialized.")

    async def on_ready(self):
        """Called when the bot successfully logs in."""
        print(f'Logged in as {self.user.name} ({self.user.id})')
        print('The DM is ready to begin the adventure!')
        print('-----------------------------------------')

    async def on_message(self, message):
        """
        Handles incoming messages on Discord.
        """
        # 1. Ignore messages from the bot itself to prevent loops
        if message.author == self.user:
            return

        # 2. Only respond if mentioned or the message starts with a command
        # This prevents the bot from replying to every single message in the channel.
        if not self.user.mentioned_in(message) and not message.content.startswith('!'):
            return

        # Clean the message content by removing the bot's mention
        user_message = message.content.replace(f'<@{self.user.id}>', '').strip()

        # 3. Handle the '!newgame' command to reset the story
        if user_message.lower() == '!newgame':
            self.game_manager.reset_history()
            await message.channel.send(
                "The mists clear, and a new adventure begins... (Conversation history has been reset). What do you do?")
            return

        # 4. Process the player's message and generate a response
        print(f"Received message from {message.author.name}: '{user_message}'")
        self.game_manager.add_message('user', f"{message.author.name} says: {user_message}")

        async with message.channel.typing():
            # Get the full history and generate the DM's response
            history = self.game_manager.get_history()
            dm_response = await self.llm.generate_response(history)

            # Add the DM's response to history for context in the next turn
            self.game_manager.add_message('model', dm_response)

            # 5. Send the response back to the Discord channel
            await message.channel.send(dm_response)


def main():
    """Main function to set up and run the bot."""
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set.")
        return

    # Initialize the components
    try:
        game_manager = GameManager(system_prompt=SYSTEM_PROMPT)
        llm_handler = LLM(api_key=GOOGLE_API_KEY)
        bot = DnDDiscordBot(llm_handler=llm_handler, game_manager=game_manager)

        # Run the bot
        bot.run(DISCORD_TOKEN)
    except ValueError as e:
        print(f"Configuration Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == '__main__':
    # For local development, you might use a .env file
    # In a cloud environment, these would be set as environment variables
    try:
        from dotenv import load_dotenv

        load_dotenv()
        DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
        GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    except ImportError:
        print("dotenv library not found, relying on system environment variables.")

    main()
