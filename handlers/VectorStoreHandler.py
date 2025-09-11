import logging
from typing import List

import chromadb
from google.api_core.exceptions import GoogleAPICallError


class VectorStoreHandler:
    """Manages interactions with a persistent ChromaDB vector store as a search index."""

    def __init__(self, embedding_model, db_path: str):
        """
        Initializes the VectorStoreHandler with a persistent ChromaDB client.

        Args:
            embedding_model: An instance of a model capable of creating embeddings.
            db_path: The file system path where the persistent database is stored.
        """
        try:
            # Use a persistent client that stores data at the specified path.
            self.client = chromadb.PersistentClient(path=db_path)
            self.embedding_model = embedding_model
            logging.info(f"ChromaDB persistent client initialized at '{db_path}'.")
        except Exception as e:
            logging.error(f"Failed to initialize ChromaDB persistent client at '{db_path}'", exc_info=e)
            raise

    async def add_or_update_entry(self, user_id: str, entry_text: str, entry_id: str):
        """
        Upserts a text entry's embedding into the vector store. The entry_id, which
        should correspond to a node in the graph DB, is used as the primary ID.

        Args:
            user_id: The unique ID of the user for namespacing within a collection.
            entry_text: The descriptive text to be embedded.
            entry_id: The unique ID of the source entity (e.g., a Neo4j node UUID).
        """
        try:
            # Get or create a unique collection for this user.
            collection = self.client.get_or_create_collection(name=f"user_{user_id}")

            embedding = await self.embedding_model.generate_embedding(entry_text)
            if not embedding:
                logging.warning(f"Skipping vector store entry '{entry_id}' due to failed embedding.")
                return

            # Use upsert to add or update the entry. We use the unique node_id from our
            # graph database as the primary ID for the vector entry.
            collection.upsert(
                embeddings=[embedding],
                documents=[entry_text],
                ids=[entry_id]
            )
            logging.info(f"Upserted entry '{entry_id}' to ChromaDB for user {user_id}.")

        except GoogleAPICallError as e:
            logging.error(f"Google API error while upserting entry '{entry_id}' for user {user_id}", exc_info=e)
        except Exception as e:
            logging.error(f"Failed to upsert entry '{entry_id}' to ChromaDB for user {user_id}", exc_info=e)

    async def query(self, user_id: str, query_text: str, n_results: int = 5) -> List[str]:
        """
        Queries the user's collection for relevant entries and returns their unique IDs.

        Returns:
            A list of strings, where each string is the unique ID of a relevant entity
            (e.g., the UUID of a node in the Neo4j graph).
        """
        try:
            collection = self.client.get_or_create_collection(name=f"user_{user_id}")

            if collection.count() == 0:
                logging.info(f"Vector store collection for user {user_id} is empty. No query performed.")
                return []

            query_embedding = await self.embedding_model.generate_embedding(query_text)
            if not query_embedding:
                return []

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )

            # We return the IDs, which are our link back to the graph database.
            neighbor_ids = results.get('ids', [[]])[0]
            logging.info(f"ChromaDB query for user {user_id} found {len(neighbor_ids)} relevant entity IDs.")
            return neighbor_ids

        except GoogleAPICallError as e:
            logging.error(f"Google API error during vector query for user {user_id}", exc_info=e)
            return []
        except Exception as e:
            logging.error(f"Failed to query ChromaDB for user {user_id}", exc_info=e)
            return []

    async def delete_user_collection(self, user_id: str):
        """
        Deletes an entire collection for a user. This is used for the !newgame command
        to ensure a complete data wipe.
        """
        try:
            self.client.delete_collection(name=f"user_{user_id}")
            logging.info(f"Successfully deleted ChromaDB collection for user {user_id}.")
        except ValueError:
            logging.warning(f"Attempted to delete non-existent ChromaDB collection for user {user_id}.")
        except Exception as e:
            logging.error(f"Failed to delete ChromaDB collection for user {user_id}", exc_info=e)

