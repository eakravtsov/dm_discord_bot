import discord
import logging
import json

from helpers.ConfigurationHelper import CHARACTER_SHEET_JSON_SCHEMA


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
        logging.info(f"Logged in as {self.user.name} ({self.user.id})")
        logging.info("The DM is ready to begin the adventure!")

    async def on_message(self, message):
        if message.author == self.user:
            return

        if not self.user.mentioned_in(message) and not message.content.startswith('!'):
            return

        user_id = str(message.author.id)
        user_message = message.content.replace(f'<@!{self.user.id}>', '').replace(f'<@{self.user.id}>', '').strip()

        if user_message.lower() == '!newgame':
            await self.game_manager.reset_history(user_id)
            await message.channel.send(
                "The mists clear, and a new adventure begins for you... (Your story has been reset). What do you do?")
            return

        if user_message.lower().startswith('!char'):
            await self.handle_char_command(message, user_message)
            return

        if user_message.lower().startswith('!genchar'):
            await self.handle_genchar_command(message, user_message)
            return

        # --- Main Game Loop ---
        log_payload = {"discord_user": message.author.name, "user_id": user_id, "message": user_message}

        # FIX: The log_payload must be wrapped in a dictionary with the key "json_fields"
        # for the Google Cloud Logging handler to process it as structured data.
        logging.info("Received message from user.", extra={'json_fields': log_payload})

        async with message.channel.typing():
            full_user_message = f"{message.author.name} says: {user_message}"
            await self.game_manager.add_message(user_id, 'user', full_user_message)

            history = await self.game_manager.get_history(user_id)
            dm_response = await self.llm.generate_response(history)

            await self.game_manager.add_message(user_id, 'model', dm_response)
            if dm_response:
                await message.channel.send(dm_response)
            else:
                logging.warning("LLM generated an empty response.")
                await message.channel.send(
                    "A strange silence fills the air... (The DM seems to have lost their train of thought.)")

    async def handle_char_command(self, message, user_message):
        """Handles the !char command to upload a character sheet."""
        try:
            parts = user_message.split('```json', 1)
            if len(parts) != 2:
                await message.channel.send(
                    "Invalid format. Please use: `!char <Character Name> \\`\\`\\`json ... \\`\\`\\``")
                return

            header = parts[0].strip().split()
            if len(header) < 2:
                await message.channel.send("Please provide a character name before the JSON block.")
                return

            character_name = " ".join(header[1:])
            json_blob = parts[1].strip().rstrip('`')
            sheet_data = json.loads(json_blob)

            final_char_name = sheet_data.get("name", character_name)
            sheet_data['name'] = final_char_name

            success = await self.game_manager.save_character_sheet(final_char_name, sheet_data)
            if success:
                await message.channel.send(f"Character sheet for **{final_char_name}** has been saved!")
            else:
                await message.channel.send(f"There was an error saving the character sheet for **{final_char_name}**.")

        except json.JSONDecodeError:
            await message.channel.send("The character sheet is not valid JSON. Please check the format.")
        except Exception as e:
            logging.error("Error handling !char command", exc_info=e)
            await message.channel.send("An unexpected error occurred while processing your character sheet.")

    async def handle_genchar_command(self, message, user_message):
        """Handles the !genchar command to generate and save a new character sheet."""
        try:
            command_parts = user_message.split(maxsplit=1)
            if len(command_parts) < 2:
                await message.channel.send("Invalid format. Please use: `!genchar <Name>, <Class>, <Race>, <Level>`")
                return

            params_str = command_parts[1]
            params = [p.strip() for p in params_str.split(',')]

            if len(params) != 4:
                await message.channel.send(
                    "Invalid format. Please provide Name, Class, Race, and Level separated by commas.")
                return

            name, char_class, race, level_str = params
            level = int(level_str)

            await message.channel.send(
                f"Generating a level {level} {race} {char_class} named **{name}**. This may take a moment...")

            async with message.channel.typing():
                sheet_data = await self.llm.generate_character_json(
                    name=name,
                    char_class=char_class,
                    race=race,
                    level=level,
                    schema=CHARACTER_SHEET_JSON_SCHEMA
                )

                if not sheet_data:
                    await message.channel.send(f"Sorry, I was unable to generate a character sheet for {name}.")
                    return

                success = await self.game_manager.save_character_sheet(name, sheet_data)

                if success:
                    summary = (
                        f"**Character sheet for {name} has been generated and saved!**\n"
                        f"**Class:** {sheet_data.get('class', 'N/A')}\n"
                        f"**Race:** {sheet_data.get('race', 'N/A')}\n"
                        f"**Level:** {sheet_data.get('level', 'N/A')}\n"
                        f"**Backstory:** {sheet_data.get('backstory', 'A mystery...')}"
                    )
                    await message.channel.send(summary)
                else:
                    await message.channel.send(f"I generated a sheet for {name}, but there was an error saving it.")

        except ValueError:
            await message.channel.send("Invalid level. Please make sure the level is a number.")
        except Exception as e:
            logging.error("Error handling !genchar command", exc_info=e)
            await message.channel.send("An unexpected error occurred while generating your character.")

