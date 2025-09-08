import time
import logging
import random
import re


def roll_dice(expression: str) -> int:
    """
    Rolls dice based on a D&D-style string expression.
    """
    if not isinstance(expression, str):
        raise TypeError("Expression must be a string.")

    components = expression.split('+')
    total_roll = 0
    dice_pattern = re.compile(r'^\s*(\d*)d(\d+)\s*$')
    modifier_pattern = re.compile(r'^\s*(\d+)\s*$')

    for component in components:
        component = component.strip()
        dice_match = dice_pattern.match(component)
        modifier_match = modifier_pattern.match(component)

        if dice_match:
            num_dice_str, num_sides_str = dice_match.groups()
            num_dice = int(num_dice_str) if num_dice_str else 1
            num_sides = int(num_sides_str)
            if num_dice < 1 or num_sides < 1:
                raise ValueError("Number of dice and sides must be at least 1.")
            for _ in range(num_dice):
                total_roll += random.randint(1, num_sides)
        elif modifier_match:
            total_roll += int(modifier_match.group(0))
        else:
            raise ValueError(f"Invalid component in expression: '{component}'")
    return total_roll


class CommandHandler:
    """Handles all user commands starting with '!'."""

    def __init__(self, game_manager, graph_handler, vector_store_handler, client):
        """
        Initializes the CommandHandler.
        Args:
            game_manager: The game manager instance.
            client: The main discord.Client instance.
        """
        self.game_manager = game_manager
        self.graph_handler = graph_handler
        self.vector_store_handler = vector_store_handler
        self.client = client
        self.commands = {
            "newgame": self.handle_newgame,
            "replay": self.handle_replay,
            "roll": self.handle_roll,
            "help": self.handle_help,
        }

    async def process_command(self, message, log_payload):
        """Routes a command to the appropriate handler method."""
        # FIX: Use self.client.user.id to get the bot's user ID
        user_message = message.content.replace(f'@Dungeon Master Bot', '').strip()
        parts = user_message[1:].lower().split()
        command = parts[0]
        args = parts[1:]

        handler = self.commands.get(command)
        if handler:
            await handler(message, args, log_payload)
        else:
            await message.channel.send(f"Unknown command: `!{command}`. Type `!help` for a list of available commands.")

    async def handle_newgame(self, message, args, log_payload):
        """
        Resets all of a user's data across all databases after a confirmation step.
        """
        user_id = str(message.author.id)
        CONFIRMATION_TIMEOUT = 30  # 30 seconds to confirm

        # Check if the user is confirming the deletion
        if args and args[0].lower() == 'confirm':
            if user_id in self.pending_confirmations:
                time_since_request = time.time() - self.pending_confirmations[user_id]

                if time_since_request <= CONFIRMATION_TIMEOUT:
                    logging.info(f"Confirmation received. Initiating full data reset for user {user_id}.",
                                 extra=log_payload)

                    try:
                        # Clear the confirmation *before* starting the deletion
                        del self.pending_confirmations[user_id]

                        # Step 1: Reset Firestore history
                        await self.game_manager.reset_history(user_id)

                        # Step 2: Delete all graph data from Neo4j
                        await self.graph_handler.delete_user_data(user_id)

                        # Step 3: Delete the entire vector collection from ChromaDB
                        await self.vector_store_handler.delete_user_collection(user_id)

                        await message.channel.send(
                            "The mists clear, and a new adventure begins for you... (Your story and world state have been completely reset). What do you do?")
                        logging.info(f"Full data reset completed for user {user_id}.", extra=log_payload)

                    except Exception as e:
                        logging.error(f"An error occurred during the new game process for user {user_id}.", exc_info=e)
                        await message.channel.send(
                            "There was an error trying to start a new game. Please try again shortly.")
                else:
                    # Confirmation has expired
                    del self.pending_confirmations[user_id]
                    await message.channel.send("Confirmation for `!newgame` has expired. Please run the command again.")
            else:
                # No pending confirmation found
                await message.channel.send("You don't have a pending `!newgame` command. Please run `!newgame` first.")
        else:
            # Initial !newgame request
            self.pending_confirmations[user_id] = time.time()
            warning_message = (
                "**Are you absolutely sure you want to start a new game?**\n"
                "This will delete your current story and all world settings - this cannot be undone.\n\n"
                f"To confirm, please type `!newgame confirm` within {CONFIRMATION_TIMEOUT} seconds."
            )
            await message.channel.send(warning_message)

    async def handle_replay(self, message, args, log_payload):
        """Replays the last message from the Dungeon Master."""
        user_id = str(message.author.id)
        history = await self.game_manager.get_history(user_id)
        last_dm_message = next((m.get('parts', [None])[0] for m in reversed(history) if m.get('role') == 'model'), None)

        if last_dm_message:
            replayed_message = f"*(Replaying last message)*\n>>> {last_dm_message}"
            await message.channel.send(replayed_message)
        else:
            await message.channel.send("There are no messages from the DM to replay yet!")
        logging.info("User replayed last message.", extra=log_payload)

    async def handle_roll(self, message, args, log_payload):
        """Rolls dice based on D&D notation."""
        if not args:
            await message.channel.send("Please provide a dice expression to roll, like `!roll 1d20+3`.")
            return

        expression = "".join(args)
        try:
            result = roll_dice(expression)
            await message.channel.send(f"{message.author.mention} rolls `{expression}` and gets: **{result}**")
            logging.info(f"User rolled '{expression}' with result {result}.", extra=log_payload)
        except (ValueError, TypeError) as e:
            await message.channel.send(f"I couldn't understand that roll. Please use D&D notation like `1d20` or `2d6+4`.\n*Error: {e}*")

    async def handle_help(self, message, args, log_payload):
        """Displays a help message with all available commands."""
        help_text = """
        **Available Commands:**
        `!newgame` - Resets your current adventure and starts a new one.
        `!replay` - Shows the last message from the Dungeon Master again.
        `!roll <notation>` - Rolls dice using D&D notation (e.g., `!roll 1d20+2d6+3`).
        `!help` - Shows this help message.

        To interact with the Dungeon Master, just `@` me and describe what you want to do!
        """
        await message.channel.send(help_text)
        logging.info("User requested help.", extra=log_payload)
