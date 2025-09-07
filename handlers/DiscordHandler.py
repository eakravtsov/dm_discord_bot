import discord
import logging

from click.shell_completion import split_arg_string


class DiscordHandler(discord.Client):
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

        log_payload = {
            "discord_user": message.author.name,
            "user_id": user_id,
            "message_length": len(user_message),
        }

        if user_message.lower() == '!newgame':
            await self.game_manager.reset_history(user_id)
            await message.channel.send(
                "The mists clear, and a new adventure begins for you... (Your story has been reset). What do you do?")
            logging.info(f"User started a new game.", extra=log_payload)
            return

        # ... inside on_message method in DiscordHandler.py

        if user_message.lower() == '!replay':
            history = await self.game_manager.get_history(user_id)

            # Search backwards for the last message from the 'model' (the DM)
            last_dm_message = None
            for message_entry in reversed(history):
                if message_entry.get('role') == 'model':
                    # Extract the actual text from the 'parts' list
                    last_dm_message = message_entry.get('parts', [None])[0]
                    break  # Stop after finding the first one

            if last_dm_message:
                replayed_message = f"*(Replaying last message)*\n>>> {last_dm_message}"
                await message.channel.send(replayed_message)
            else:
                await message.channel.send("There are no messages from the DM to replay yet!")
            return  # Make sure to return after handling the command

        logging.info(f"Received message: '{user_message}'", extra=log_payload)

        async with message.channel.typing():
            try:
                await self.game_manager.add_message(user_id, 'user', f"{message.author.name} says: {user_message}")
                history = await self.game_manager.get_history(user_id)
                dm_response = await self.llm.generate_response(history)
                await self.game_manager.add_message(user_id, 'model', dm_response)
                chunks = split_string_by_word_chunks(dm_response, 1900)
                for chunk in chunks:
                    await message.channel.send(chunk)
            except Exception as e:
                logging.error(f"An error occurred while processing a message for user {user_id}", exc_info=e)
                await message.channel.send("A strange energy crackles, and the world seems to pause. I need a moment to gather my thoughts. Please try again shortly.")


def split_string_by_word_chunks(text, max_length):
    words = text.split()  # Split the string into words
    chunks = []
    current_chunk = ""

    for word in words:
        # Check if adding the current word (plus a space if needed) exceeds max_length
        if current_chunk and len(current_chunk) + 1 + len(word) > max_length:
            chunks.append(current_chunk.strip())  # Add the completed chunk
            current_chunk = word  # Start a new chunk with the current word
        else:
            if current_chunk:
                current_chunk += " " + word
            else:
                current_chunk = word

    if current_chunk:  # Add any remaining part of the string as a chunk
        chunks.append(current_chunk.strip())

    return chunks

