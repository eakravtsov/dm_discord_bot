import discord
import logging

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

        logging.info(f"Received message: '{user_message}'", extra=log_payload)

        async with message.channel.typing():
            try:
                await self.game_manager.add_message(user_id, 'user', f"{message.author.name} says: {user_message}")
                history = await self.game_manager.get_history(user_id)
                dm_response = await self.llm.generate_response(history)
                await self.game_manager.add_message(user_id, 'model', dm_response)
                await message.channel.send(dm_response)
            except Exception as e:
                logging.error(f"An error occurred while processing a message for user {user_id}", exc_info=e)
                await message.channel.send("A strange energy crackles, and the world seems to pause. I need a moment to gather my thoughts. Please try again shortly.")
