import discord
import logging

from handlers.CommandHandler import CommandHandler


class DiscordHandler(discord.Client):
    """The main Discord bot class that ties everything together."""

    def __init__(self, llm_handler, game_manager, **options):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents, **options)
        self.llm = llm_handler
        self.game_manager = game_manager
        self.command_handler = CommandHandler(game_manager)
        logging.info("Discord Bot initialized.")

    async def on_ready(self):
        logging.info(f'Logged in as {self.user.name} ({self.user.id})')
        logging.info('The DM is ready to begin the adventure!')

    async def on_message(self, message):
        if message.author == self.user:
            return

        user_message_raw = message.content
        if not self.user.mentioned_in(message) and not user_message_raw.strip().startswith('!'):
            return

        user_id = str(message.author.id)
        user_message = user_message_raw.replace(f'<@{self.user.id}>', '').strip()

        log_payload = {
            "discord_user": message.author.name,
            "user_id": user_id,
            "message_length": len(user_message),
        }

        # If the message is a command, process it and stop further execution
        if user_message.startswith('!'):
            await self.command_handler.process_command(message, log_payload)
            return

        # Otherwise, process it as a regular game message
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
                await message.channel.send(
                    "A strange energy crackles, and the world seems to pause. I need a moment to gather my thoughts. Please try again shortly.")


def split_string_by_word_chunks(text, max_length):
    words = text.split()
    chunks = []
    current_chunk = ""

    for word in words:
        if current_chunk and len(current_chunk) + 1 + len(word) > max_length:
            chunks.append(current_chunk.strip())
            current_chunk = word
        else:
            if current_chunk:
                current_chunk += " " + word
            else:
                current_chunk = word

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
