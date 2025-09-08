import discord
import logging
from handlers.CommandHandler import CommandHandler


class DiscordHandler(discord.Client):
    """The main Discord bot class that orchestrates the RAG workflow."""

    def __init__(self, llm_handler, game_manager, graph_handler, vector_store_handler, **options):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents, **options)

        self.llm = llm_handler
        self.game_manager = game_manager
        self.graph_handler = graph_handler
        self.vector_store_handler = vector_store_handler
        self.command_handler = CommandHandler(game_manager, self)
        logging.info("Discord Bot initialized with all handlers.")

    async def on_ready(self):
        logging.info(f'Logged in as {self.user.name} ({self.user.id})')

    async def on_message(self, message):
        if message.author == self.user:
            return
        if not self.user.mentioned_in(message) and not message.content.strip().startswith('!'):
            return

        user_id = str(message.author.id)
        user_message = message.content.replace(f'<@{self.user.id}>', '').strip()
        log_payload = {"discord_user": message.author.name, "user_id": user_id}

        if user_message.startswith('!'):
            await self.command_handler.process_command(message, log_payload)
            return

        logging.info(f"Received message: '{user_message}'", extra=log_payload)
        async with message.channel.typing():
            try:
                # --- RAG Workflow ---
                # 1. RETRIEVE relevant entity names from Vector Store
                relevant_entity_names = await self.vector_store_handler.query(user_id, user_message)

                # 2. AUGMENT context by fetching entity details from Graph DB
                context_str = ""
                if relevant_entity_names:
                    logging.info(f"Found relevant entities: {relevant_entity_names}", extra=log_payload)
                    context_parts = [await self.graph_handler.get_entity_context(user_id, name) for name in
                                     relevant_entity_names]
                    context_str = "\n\n".join(filter(None, context_parts))

                # 3. GENERATE response with augmented context
                await self.game_manager.add_message(user_id, 'user', f"{message.author.name} says: {user_message}")
                history = await self.game_manager.get_history(user_id)
                dm_response = await self.llm.generate_response(history, context_str)
                await self.game_manager.add_message(user_id, 'model', dm_response)

                # 4. SEND response to user
                for chunk in split_string_by_word_chunks(dm_response, 1900):
                    await message.channel.send(chunk)

                # 5. EXTRACT new facts from the latest turn
                conversation_chunk = f"Player: {user_message}\nDM: {dm_response}"
                new_entities = await self.llm.extract_facts(conversation_chunk)

                if new_entities:
                    for entity in new_entities:
                        # 6. UPDATE Knowledge Graph
                        await self.graph_handler.add_or_update_entity(user_id, entity)

                        # 7. UPDATE Search Index (Vector Store)
                        sentence = self._generate_descriptive_sentence(entity)
                        await self.vector_store_handler.add_entry(user_id, sentence)

            except Exception as e:
                logging.error(f"An error occurred in RAG workflow for user {user_id}", exc_info=e)
                await message.channel.send("A strange energy crackles... I need a moment. Please try again.")

    def _generate_descriptive_sentence(self, entity: dict) -> str:
        """Flattens a structured entity into a single sentence for embedding."""
        name = entity.get("name")
        e_type = entity.get("type")
        props = entity.get("properties", {})

        description = f"{e_type}: {name}"
        if props:
            prop_list = [f"{key.replace('_', ' ')} is {value}" for key, value in props.items()]
            description += " where " + ", ".join(prop_list)
        return description + "."


def split_string_by_word_chunks(text, max_length):
    words = text.split()
    chunks, current_chunk = [], ""
    for word in words:
        if current_chunk and len(current_chunk) + len(word) + 1 > max_length:
            chunks.append(current_chunk)
            current_chunk = word
        else:
            current_chunk += (" " if current_chunk else "") + word
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

