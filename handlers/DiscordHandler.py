import discord
import logging
import re

from handlers.CommandHandler import CommandHandler, DiceRollView


class DiscordHandler(discord.Client):
    """The main Discord bot class that ties everything together."""

    def __init__(self, llm_handler, game_manager, graph_handler, vector_store_handler, **options):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents, **options)
        self.llm = llm_handler
        self.game_manager = game_manager
        self.graph_handler = graph_handler
        self.vector_store_handler = vector_store_handler
        self.command_handler = CommandHandler(game_manager, graph_handler, vector_store_handler, self)
        logging.info("Discord Bot initialized.")

    async def on_ready(self):
        logging.info(f'Logged in as {self.user.name} ({self.user.id})')
        logging.info('The DM is ready to begin the adventure!')

    def _create_descriptive_sentence(self, entity: dict) -> str:
        """Creates a context-rich sentence from a structured entity dictionary."""
        name = entity.get("name", "Unnamed Entity")
        ent_type = entity.get("type", "Thing")

        props = []
        for key, value in entity.get("properties", {}).items():
            props.append(f"its {key} is {value}")

        if not props:
            return f"{ent_type}: {name}."

        return f"{ent_type}: {name} is an entity whose " + ", and ".join(props) + "."

    async def on_message(self, message):
        if message.author == self.user:
            return

        user_message_raw = message.content
        if not self.user.mentioned_in(message) and not user_message_raw.strip().startswith('!'):
            return

        user_id = str(message.author.id)

        # This will be our initial message to process.
        # It can be updated later by an automated dice roll.
        message_to_process = user_message_raw.replace(f'<@{self.user.id}>', '').strip()

        # The main loop. It will run once for a normal message, and multiple
        # times if an automated action (like a dice roll) occurs.
        while message_to_process:
            log_payload = {
                "discord_user": message.author.name,
                "user_id": user_id,
                "message_length": len(message_to_process),
            }

            if message_to_process.startswith('!'):
                await self.command_handler.process_command(message, log_payload)
                return  # Exit after a command

            logging.info(f"Processing message: '{message_to_process}'", extra=log_payload)

            try:
                async with message.channel.typing():
                    # --- Read/Retrieval Phase ---
                    relevant_entity_ids = await self.vector_store_handler.query(user_id, message_to_process)
                    context_string = ""
                    if relevant_entity_ids:
                        context_items = []
                        for entity_id in relevant_entity_ids:
                            context = await self.graph_handler.get_entity_context(user_id, entity_id)
                            if context:
                                context_items.append(context)
                        if context_items:
                            context_string = "\n".join(context_items)

                    # --- Augmented Generation Phase ---
                    # Use the message_to_process in the history
                    await self.game_manager.add_message(user_id, 'user',
                                                        f"{message.author.name} says: {message_to_process}")
                    history = await self.game_manager.get_history(user_id)
                    dm_response = await self.llm.generate_response(history, context_string)
                    await self.game_manager.add_message(user_id, 'model', dm_response)

                    # --- Respond to User (with potential UI) ---
                    chunks = split_string_by_word_chunks(dm_response, 1900)
                    view_to_send = None

                    roll_keywords = ["make a roll", "roll a", "make a check", "roll for"]
                    if any(keyword in dm_response.lower() for keyword in roll_keywords):
                        view_to_send = DiceRollView(author=message.author)

                    for i, chunk in enumerate(chunks):
                        if i == len(chunks) - 1:
                            await message.channel.send(chunk, view=view_to_send)
                        else:
                            await message.channel.send(chunk)

                    # --- Write/Memory Phase ---
                    conversation_chunk = f"Player: {message_to_process}\nDM: {dm_response}"
                    entities = await self.llm.extract_facts(conversation_chunk)

                    if entities:
                        for entity in entities:
                            node_id = await self.graph_handler.add_or_update_entity(user_id, entity)
                            if node_id:
                                sentence = self._create_descriptive_sentence(entity)
                                await self.vector_store_handler.add_or_update_entry(user_id, sentence, node_id)

                    # --- Loop continuation logic ---
                    if view_to_send:
                        # Wait for the user to click a button
                        await view_to_send.interaction_complete.wait()
                        # The view now has the result. Set it as the next message to process.
                        message_to_process = view_to_send.roll_result_message
                    else:
                        # If no view was sent, there's no automatic follow-up. Exit the loop.
                        message_to_process = None

            except Exception as e:
                logging.error(f"An error occurred in RAG workflow for user {user_id}", exc_info=e)
                await message.channel.send(
                    "A strange energy crackles, and the world seems to pause. I need a moment to gather my thoughts. Please try again shortly.")
                # Exit loop on error
                message_to_process = None


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

