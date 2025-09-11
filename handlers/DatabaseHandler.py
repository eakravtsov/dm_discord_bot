import logging
from google.cloud import firestore

# Configuration for history summarization
HISTORY_LIMIT = 100
TURNS_TO_KEEP = 6


class DatabaseHandler:
    """
    Manages conversation history and orchestrates the periodic world-state
    consolidation to the graph and vector databases.
    """

    def __init__(self, project_id, system_prompt, database_id="dnd-game-history-database"):
        self.system_prompt = system_prompt
        self.db = None
        # These will be set after initialization to avoid circular dependencies
        self.llm_handler = None
        self.graph_handler = None
        self.vector_store_handler = None

        if not project_id:
            logging.error("GCP_PROJECT_ID was not provided.")
            return

        try:
            self.db = firestore.AsyncClient(project=project_id, database=database_id)
            self.sessions_collection = self.db.collection('dnd_sessions')
            logging.info(f"Firestore initialized successfully for database '{database_id}'.")
        except Exception as e:
            logging.critical(f"Fatal error initializing Firestore: {e}", exc_info=e)
            self.db = None

    def set_handlers(self, llm_handler, graph_handler, vector_store_handler):
        """Sets the other handlers needed for world-state updates."""
        self.llm_handler = llm_handler
        self.graph_handler = graph_handler
        self.vector_store_handler = vector_store_handler

    def is_initialized(self):
        return self.db is not None

    def _get_initial_history(self):
        return [{'role': 'user', 'parts': [self.system_prompt]},
                {'role': 'model', 'parts': ["Understood. The world is ready. I will await the adventurers."]}
                ]

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

    async def _ensure_user_document_exists(self, user_id):
        user_doc_ref = self.sessions_collection.document(str(user_id))
        doc_snapshot = await user_doc_ref.get()
        if not doc_snapshot.exists:
            logging.info(f"No document for user {user_id}. Creating new game.")
            await user_doc_ref.set({'history': self._get_initial_history()})
        return user_doc_ref

    async def get_history(self, user_id):
        user_doc_ref = await self._ensure_user_document_exists(user_id)
        doc = await user_doc_ref.get()
        return doc.to_dict().get('history', self._get_initial_history())

    async def add_message(self, user_id, role, message):
        current_history = await self.get_history(user_id)
        if len(current_history) >= HISTORY_LIMIT:
            await self._truncate_and_update_world_state(user_id, current_history)

        user_doc_ref = await self._ensure_user_document_exists(user_id)
        update_data = {'history': firestore.ArrayUnion([{'role': role, 'parts': [message]}])}
        await user_doc_ref.update(update_data)

    async def reset_history(self, user_id):
        user_doc_ref = self.sessions_collection.document(str(user_id))
        await user_doc_ref.set({'history': self._get_initial_history()})
        logging.info(f"History reset for user {user_id}.")

    async def overwrite_history(self, user_id, new_history):
        user_doc_ref = self.sessions_collection.document(str(user_id))
        try:
            await user_doc_ref.set({'history': new_history})
            logging.info(f"Successfully overwrote history for user {user_id} after summarization.")
            return True
        except Exception as e:
            logging.error(f"Failed to overwrite history for user {user_id}.", exc_info=e)
            return False

    async def _truncate_and_update_world_state(self, user_id, history):
        if not all([self.llm_handler, self.graph_handler, self.vector_store_handler]):
            logging.error("One or more handlers are not set. Cannot update world state.")
            return

        logging.info(f"History limit reached for user {user_id}. Consolidating world state.")

        system_prompt = history[0]
        recent_conversation = history[-TURNS_TO_KEEP:]
        conversation_to_analyze = history[1:-TURNS_TO_KEEP]

        # 1. Extract the structured world state
        entities = await self.llm_handler.extract_world_state_from_history(conversation_to_analyze)

        # 2. Update the databases with the new entity data
        if entities:
            logging.info(f"Updating databases with {len(entities)} entities for user {user_id}.")
            for entity in entities:
                try:
                    node_id = await self.graph_handler.add_or_update_entity(user_id, entity)
                    if node_id:
                        sentence = self._create_descriptive_sentence(entity)
                        await self.vector_store_handler.add_or_update_entry(user_id, sentence, node_id)
                except Exception as e:
                    logging.error(f"Failed to process entity: {entity.get('name')}", exc_info=e)

        # 3. Generate the chat summary for the history log
        summary = await self.llm_handler.summarize_history(conversation_to_analyze)

        # 4. Create the new, truncated history
        new_history = [
            system_prompt,
            {'role': 'user', 'parts': [f"[The story so far: {summary}]"]},
            {'role': 'model', 'parts': ["Understood. Let's continue."]},
            *recent_conversation
        ]

        await self.overwrite_history(user_id, new_history)
