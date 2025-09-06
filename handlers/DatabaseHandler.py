import logging
from google.cloud import firestore

class DatabaseHandler:
    """Manages game state and conversation history using Firestore."""

    def __init__(self, project_id, system_prompt):
        """Initializes the database handler and Firestore client."""
        self.system_prompt = system_prompt
        self.db = self._initialize_firestore(project_id)
        if self.db:
            self.collection_ref = self.db.collection('dnd_sessions')

    def _initialize_firestore(self, project_id):
        """Initializes and returns a Firestore AsyncClient."""
        if not project_id:
            logging.error("GCP_PROJECT_ID environment variable not set.")
            return None
        try:
            db = firestore.AsyncClient(project=project_id, database="dnd-game-history-database")
            logging.info("Firestore initialized successfully for database 'dnd-game-history-database'.")
            return db
        except Exception as e:
            logging.error(f"Error initializing Firestore: {e}", exc_info=e)
            return None

    def is_initialized(self):
        """Returns True if the Firestore client was initialized successfully."""
        return self.db is not None

    def _get_initial_history(self):
        """Returns the initial history for a new game."""
        return [{'role': 'user', 'parts': [self.system_prompt]},
                {'role': 'model', 'parts': ["Understood. The world is ready. I will await the adventurers."]}
                ]

    async def _ensure_user_document_exists(self, user_id):
        """Creates a document for a user if it doesn't already exist."""
        user_doc_ref = self.collection_ref.document(str(user_id))
        doc = await user_doc_ref.get()
        if not doc.exists:
            logging.info(f"No history found for user {user_id}. Creating new game document.")
            initial_history = self._get_initial_history()
            await user_doc_ref.set({'history': initial_history})
        return user_doc_ref

    async def get_history(self, user_id):
        """Retrieves the conversation history for a specific user from Firestore."""
        user_doc_ref = await self._ensure_user_document_exists(user_id)
        doc = await user_doc_ref.get()
        return doc.to_dict().get('history', self._get_initial_history())

    async def add_message(self, user_id, role, message):
        """Adds a message to a user's conversation history in Firestore."""
        user_doc_ref = await self._ensure_user_document_exists(user_id)
        update_data = {'history': firestore.ArrayUnion([{'role': role, 'parts': [message]}])}
        await user_doc_ref.update(update_data)

    async def reset_history(self, user_id):
        """Resets a user's history in Firestore to the initial state."""
        user_doc_ref = self.collection_ref.document(str(user_id))
        initial_history = self._get_initial_history()
        await user_doc_ref.set({'history': initial_history})
        logging.info(f"History reset for user {user_id}.")
