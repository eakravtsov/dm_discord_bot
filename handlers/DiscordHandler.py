import discord
import logging
import re
import asyncio

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

    async def _run_rag_cycle(self, user_id: str, author: discord.User, message_to_process: str):
        """
        Runs a full RAG cycle: Retrieve, Augment, Generate.
        Returns the DM's response and any UI view to be sent.
        """
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
        await self.game_manager.add_message(user_id, 'user', f"{author.name} says: {message_to_process}")
        history = await self.game_manager.get_history(user_id)
        dm_response = await self.llm.generate_response(history, context_string)
        await self.game_manager.add_message(user_id, 'model', dm_response)

        # --- Determine if UI is needed ---
        view_to_send = None
        roll_keywords = ["make a", "roll a", "roll for"]
        if any(keyword in dm_response.lower() for keyword in roll_keywords):
            view_to_send = DiceRollView(author=author)

        return dm_response, view_to_send

    async def on_message(self, message):
        if message.author == self.user:
            return

        user_message_raw = message.content
        if not self.user.mentioned_in(message) and not user_message_raw.strip().startswith('!'):
            return

        user_id = str(message.author.id)
        message_to_process = user_message_raw.replace(f'<@{self.user.id}>', '').strip()

        # Handle commands separately
        if message_to_process.startswith('!'):
            log_payload = {"discord_user": message.author.name, "user_id": user_id}
            await self.command_handler.process_command(message, log_payload)
            return

        # --- Main Game Loop ---
        try:
            # Loop continues as long as there is an automated action (like a dice roll)
            while message_to_process:
                log_payload = {
                    "discord_user": message.author.name, "user_id": user_id, "message_length": len(message_to_process)
                }
                logging.info(f"Processing message: '{message_to_process}'", extra=log_payload)

                dm_response = None
                view_to_send = None

                # --- Generation Phase (Typing indicator is active here) ---
                async with message.channel.typing():
                    dm_response, view_to_send = await self._run_rag_cycle(user_id, message.author, message_to_process)

                # --- Send Response Phase (Typing indicator is now off) ---
                if dm_response:
                    chunks = split_string_by_word_chunks(dm_response, 1900)
                    for i, chunk in enumerate(chunks):
                        if i == len(chunks) - 1:  # Attach view only to the last chunk
                            await message.channel.send(chunk, view=view_to_send)
                        else:
                            await message.channel.send(chunk)

                # --- Silent Write/Memory Phase (No typing indicator) ---
                conversation_chunk = f"Player: {message_to_process}\nDM: {dm_response}"
                entities = await self.llm.extract_facts(conversation_chunk)
                if entities:
                    for entity in entities:
                        node_id = await self.graph_handler.add_or_update_entity(user_id, entity)
                        if node_id:
                            sentence = self._create_descriptive_sentence(entity)
                            await self.vector_store_handler.add_or_update_entry(user_id, sentence, node_id)

                # --- Loop Continuation Logic ---
                if view_to_send:
                    await view_to_send.interaction_complete.wait()
                    message_to_process = view_to_send.roll_result_message
                else:
                    message_to_process = None  # Exit loop if no UI was sent

        except Exception as e:
            logging.error(f"An error occurred in main workflow for user {user_id}", exc_info=e)
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

