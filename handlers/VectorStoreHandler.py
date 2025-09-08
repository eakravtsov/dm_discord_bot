import chromadb
import logging
from google.api_core.exceptions import GoogleAPICallError


class VectorStoreHandler:
    """Manages interactions with a persistent ChromaDB vector store."""

    def __init__(self, embedding_model, db_path: str):
        """
        Initializes the VectorStoreHandler with a persistent client.

        Args:
            embedding_model: An instance of a model capable of creating embeddings.
            db_path: The file system path to store the persistent database.
        """
        try:
            # Use a persistent client that stores data at the specified path.
            self.client = chromadb.PersistentClient(path=db_path)
            self.embedding_model = embedding_model
            logging.info(f"ChromaDB persistent client initialized at '{db_path}'.")
        except Exception as e:
            logging.error(f"Failed to initialize ChromaDB persistent client at '{db_path}'", exc_info=e)
            raise

    async def add_entry(self, user_id: str, entry: str):
        """
        Adds a new text entry to the user's collection in the vector store.

        Args:
            user_id: The unique ID of the user.
            entry: The string of text (a fact, description, etc.) to add.
        """
        try:
            # Get or create a unique collection for this user.
            collection = self.client.get_or_create_collection(name=f"user_{user_id}")

            embedding = await self.embedding_model.generate_embedding(entry)

            # Use the entry itself as a unique ID.
            collection.add(
                embeddings=[embedding],
                documents=[entry],
                ids=[entry]
            )
            logging.info(f"Added new entry to vector store for user {user_id}: '{entry}'")
        except GoogleAPICallError as e:
            logging.error(f"Google API error while generating embedding for user {user_id}", exc_info=e)
        except Exception as e:
            logging.error(f"Failed to add entry to vector store for user {user_id}", exc_info=e)

    async def query(self, user_id: str, query_text: str, n_results: int = 3) -> list:
        """
        Queries the user's collection for relevant entries based on a query string.

        Args:
            user_id: The unique ID of the user.
            query_text: The text to search for (e.g., the user's latest message).
            n_results: The number of top results to return.

        Returns:
            A list of the most relevant document strings.
        """
        try:
            collection = self.client.get_or_create_collection(name=f"user_{user_id}")

            if collection.count() == 0:
                return []

            query_embedding = await self.embedding_model.generate_embedding(query_text)

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            return results.get('documents', [[]])[0]
        except GoogleAPICallError as e:
            logging.error(f"Google API error during vector query for user {user_id}", exc_info=e)
            return []
        except Exception as e:
            logging.error(f"Failed to query vector store for user {user_id}", exc_info=e)
            return []
