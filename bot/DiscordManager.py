import os
import discord

from dotenv import load_dotenv

class DiscordManager(discord.Client):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        # Initialize the parent Client class with our intents
        super().__init__(intents=intents)

    async def on_ready(self):
        """This function is called when the bot is connected and ready."""
        print(f'✅ Logged in as {self.user} (ID: {self.user.id})')
        print('Bot is ready to receive DMs.')

    async def on_message(self, message: discord.Message):
        """This function is called every time a message is sent."""
        # 1. Ignore messages sent by the bot itself to prevent loops
        if message.author == self.user:
            return

        # 2. Check if the message was sent in a DM channel
        if isinstance(message.channel, discord.DMChannel):
            print(f"📬 Received DM from {message.author}: '{message.content}'")

            # 3. Reply to the DM
            await message.channel.send("MESSAGE RECEIVED")


# This is the main part of the script that runs the bot
if __name__ == "__main__":

    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")

    if token is None:
        print("🛑 ERROR: DISCORD_TOKEN environment variable not found.")
        print("Please set it before running the bot.")
    else:
        # Create an instance of our bot and run it
        bot = DiscordManager()
        bot.run(token)
