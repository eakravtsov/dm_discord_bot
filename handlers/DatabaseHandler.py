import logging
from google.cloud import firestore

# --- Configuration for history summarization ---
HISTORY_LIMIT = 100  # Number of entries before summarization is triggered
TURNS_TO_KEEP = 6  # Keep the last 6 entries (3 player, 3 model) for context


class DatabaseHandler:
    """
    Manages conversation history and triggers its own truncation when the
    history grows too long.
    """

    def __init__(self, project_id, system_prompt, database_id="dnd-game-history-database"):
        self.system_prompt = system_prompt
        self.db = None
        # This will be set after initialization to avoid circular dependencies
        self.llm_handler = None

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

    def set_llm_handler(self, llm_handler):
        """Sets the LLM handler after initialization to allow for summarization."""
        self.llm_handler = llm_handler

    def is_initialized(self):
        """Checks if the Firestore client was initialized successfully."""
        return self.db is not None

    def _get_initial_history(self):
        """Returns the initial history for a new game."""
        return [{'role': 'user', 'parts': [self.system_prompt]},
                {'role': 'model', 'parts': ["Understood. The world is ready. I will await the adventurers."]}
                ]

    async def _ensure_user_document_exists(self, user_id):
        """Creates a user document if it doesn't exist."""
        user_doc_ref = self.sessions_collection.document(str(user_id))
        doc_snapshot = await user_doc_ref.get()
        if not doc_snapshot.exists:
            logging.info(f"No document for user {user_id}. Creating new game.")
            initial_history = self._get_initial_history()
            await user_doc_ref.set({'history': initial_history})
        return user_doc_ref

    async def get_history(self, user_id):
        """Retrieves the conversation history for a specific user."""
        user_doc_ref = await self._ensure_user_document_exists(user_id)
        doc = await user_doc_ref.get()
        return doc.to_dict().get('history', self._get_initial_history())

    async def add_message(self, user_id, role, message):
        """
        Adds a message to a user's conversation history, performing truncation first if needed.
        """
        # --- Truncation Logic ---
        # First, check if truncation is needed *before* adding the new message.
        current_history = await self.get_history(user_id)
        if len(current_history) >= HISTORY_LIMIT:
            await self._truncate_history(user_id, current_history)

        # Now, add the new message to the potentially truncated history.
        user_doc_ref = await self._ensure_user_document_exists(user_id)
        update_data = {'history': firestore.ArrayUnion([{'role': role, 'parts': [message]}])}
        await user_doc_ref.update(update_data)

    async def reset_history(self, user_id):
        """Resets a user's history to the initial state."""
        user_doc_ref = self.sessions_collection.document(str(user_id))
        initial_history = self._get_initial_history()
        await user_doc_ref.set({'history': initial_history})
        logging.info(f"History reset for user {user_id}.")

    async def overwrite_history(self, user_id, new_history):
        """Overwrites the entire history for a user with a new one."""
        user_doc_ref = self.sessions_collection.document(str(user_id))
        try:
            await user_doc_ref.set({'history': new_history})
            logging.info(f"Successfully overwrote history for user {user_id} after summarization.")
            return True
        except Exception as e:
            logging.error(f"Failed to overwrite history for user {user_id}.", exc_info=e)
            return False

    async def _truncate_history(self, user_id, history):
        """Internal method to perform the history summarization and overwrite."""
        if not self.llm_handler:
            logging.error("LLM handler not set on DatabaseHandler. Cannot summarize history.")
            return

        logging.info(f"History for user {user_id} has reached {len(history)} entries. Starting summarization.")

        system_prompt = history[0]
        recent_conversation = history[-TURNS_TO_KEEP:]
        conversation_to_summarize = history[1:-TURNS_TO_KEEP]

        summary = await self.llm_handler.summarize_history(conversation_to_summarize)

        new_history = [
            system_prompt,
            {'role': 'user', 'parts': [f"[The story so far: {summary}]"]},
            {'role': 'model', 'parts': ["Understood. Let's continue."]},
            *recent_conversation
        ]

        await self.overwrite_history(user_id, new_history)

