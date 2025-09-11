import discord
import logging

from handlers.CommandHandler import CommandHandler


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
        # Pass the current instance 'self' to the CommandHandler
        self.command_handler = CommandHandler(game_manager, graph_handler, vector_store_handler, self)
        logging.info("Discord Bot initialized.")

    async def on_ready(self):
        logging.info(f'Logged in as {self.user.name} ({self.user.id})')
        logging.info('The DM is ready to begin the adventure!')

    async def process_narrative_message(self, original_message, message_to_process):
        """
        The core RAG and LLM processing loop for any narrative action.
        This can be called by a user's chat message or an automated command result.
        """
        user_id = str(original_message.author.id)
        log_payload = {
            "discord_user": original_message.author.name,
            "user_id": user_id,
            "message_length": len(message_to_process),
        }
        logging.info(f"Processing narrative message: '{message_to_process}'", extra=log_payload)

        try:
            dm_response = None
            async with original_message.channel.typing():
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
                await self.game_manager.add_message(user_id, 'user',
                                                    f"{original_message.author.name} says: {message_to_process}")
                history = await self.game_manager.get_history(user_id)
                dm_response = await self.llm.generate_response(history, context_string)

                await self.game_manager.add_message(user_id, 'model', dm_response)

            # --- Send Response Phase ---
            if dm_response:
                chunks = split_string_by_word_chunks(dm_response, 1900)
                for chunk in chunks:
                    await original_message.channel.send(chunk)

        except Exception as e:
            logging.error(f"An error occurred in narrative processing for user {user_id}", exc_info=e)
            await original_message.channel.send(
                "A strange energy crackles, and the world seems to pause. I need a moment to gather my thoughts. Please try again shortly.")

    async def on_message(self, message):
        if message.author == self.user:
            return

        user_message_raw = message.content
        if not self.user.mentioned_in(message) and not user_message_raw.strip().startswith('!'):
            return

        user_message = user_message_raw.replace(f'<@{self.user.id}>', '').strip()
        log_payload = {"discord_user": message.author.name, "user_id": str(message.author.id)}

        # --- Route to the correct handler ---
        if user_message.startswith('!'):
            await self.command_handler.process_command(message, log_payload)
        else:
            await self.process_narrative_message(message, user_message)


def split_string_by_word_chunks(text, max_length):
    # ... (function remains the same)
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

