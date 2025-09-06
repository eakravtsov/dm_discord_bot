import logging
from google.cloud import firestore


class DatabaseHandler:
    """Manages game state and conversation history using Firestore."""

    def __init__(self, project_id, system_prompt, database_name="dnd-game-history-database"):
        """
        Initializes the database handler. Now takes a project_id and
        creates the Firestore client internally.
        """
        self.system_prompt = system_prompt
        self.db = None  # Initialize db as None

        if not project_id:
            logging.error("GCP_PROJECT_ID was not provided.")
            return

        try:
            self.db = firestore.AsyncClient(project=project_id, database=database_name)
            logging.info(f"Firestore initialized successfully for database '{database_name}'.")
            self.collection_ref = self.db.collection('dnd_sessions')
        except Exception as e:
            logging.critical(f"Fatal error initializing Firestore: {e}", exc_info=e)
            self.db = None  # Ensure db is None on failure

    def is_initialized(self):
        """Checks if the Firestore client was initialized successfully."""
        return self.db is not None

    def _get_initial_history(self):
        """Returns the initial history for a new game."""
        return [{'role': 'user', 'parts': [self.system_prompt]},
                {'role': 'model', 'parts': ["Understood. The world is ready. I will await the adventurers."]}
                ]

    async def _ensure_user_document_exists(self, user_id):
        """
        Checks if a user's document exists and creates it if not.
        """
        user_doc_ref = self.collection_ref.document(str(user_id))
        try:
            @firestore.async_transactional
            async def check_and_create(transaction):
                doc_snapshot = await user_doc_ref.get(transaction=transaction)
                if not doc_snapshot.exists:
                    initial_history = self._get_initial_history()
                    transaction.set(user_doc_ref, {'history': initial_history})
                    logging.info(f"No history found for user {user_id}. Creating new game document.")

            await self.db.transaction()(check_and_create)
            return user_doc_ref
        except Exception as e:
            logging.error(f"Error ensuring document exists for user {user_id}", exc_info=e)
            return None

    async def get_history(self, user_id):
        """Retrieves the conversation history for a specific user."""
        user_doc_ref = await self._ensure_user_document_exists(user_id)
        if not user_doc_ref:
            return self._get_initial_history()

        doc = await user_doc_ref.get()
        return doc.to_dict().get('history', self._get_initial_history())

    async def add_message(self, user_id, role, message):
        """Adds a message to a user's conversation history."""
        user_doc_ref = await self._ensure_user_document_exists(user_id)
        if user_doc_ref:
            update_data = {'history': firestore.ArrayUnion([{'role': role, 'parts': [message]}])}
            await user_doc_ref.update(update_data)

    async def reset_history(self, user_id):
        """Resets a user's history to the initial state."""
        user_doc_ref = self.collection_ref.document(str(user_id))
        initial_history = self._get_initial_history()
        await user_doc_ref.set({'history': initial_history})
        logging.info(f"History reset for user {user_id}.")

