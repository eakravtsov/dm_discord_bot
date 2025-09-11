import logging
from google.cloud import aiplatform
from google.api_core.exceptions import GoogleAPICallError


class VectorStoreHandler:
    """Manages interactions with Vertex AI Vector Search as a search index."""

    def __init__(self, project_id: str, region: str, endpoint_id: str, embedding_model):
        """Initializes the VectorStoreHandler."""
        try:
            aiplatform.init(project=project_id, location=region)
            self.index_endpoint = aiplatform.MatchingEngineIndexEndpoint(endpoint_id)
            self.embedding_model = embedding_model
            logging.info(f"Vertex AI Vector Search client initialized for endpoint '{endpoint_id}'.")
        except Exception as e:
            logging.error("Failed to initialize Vertex AI Vector Search client.", exc_info=e)
            raise

    async def add_or_update_entry(self, user_id: str, entry_text: str, entry_id: str):
        """
        Upserts a text entry's embedding into the vector store.

        Args:
            user_id: The unique ID of the user for namespacing.
            entry_text: The descriptive text to be embedded.
            entry_id: The unique ID of the source entity (e.g., a Neo4j node UUID).
        """
        try:
            embedding = await self.embedding_model.generate_embedding(entry_text)
            if not embedding:
                logging.warning(f"Skipping vector store entry '{entry_id}' due to failed embedding.")
                return

            datapoint = aiplatform.MatchingEngineIndexDatapoint(
                datapoint_id=entry_id,
                feature_vector=embedding,
                restricts=[
                    aiplatform.IndexDatapoint.Restriction(
                        namespace="user_id", allow_list=[user_id]
                    )
                ]
            )

            # upsert_datapoints creates the entry if the ID is new, or updates it if it exists.
            self.index_endpoint.upsert_datapoints(datapoints=[datapoint])
            logging.info(f"Upserted entry '{entry_id}' to Vertex AI for user {user_id}.")

        except GoogleAPICallError as e:
            logging.error(f"Google API error while upserting entry '{entry_id}' for user {user_id}", exc_info=e)
        except Exception as e:
            logging.error(f"Failed to upsert entry '{entry_id}' to Vertex AI for user {user_id}", exc_info=e)

    async def query(self, user_id: str, query_text: str, n_results: int = 5) -> list[str]:
        """
        Queries the user's namespace and returns a list of relevant entity IDs.

        Returns:
            A list of strings, where each string is the unique ID of a relevant entity.
        """
        try:
            query_embedding = await self.embedding_model.generate_embedding(query_text)
            if not query_embedding:
                return []

            results = self.index_endpoint.find_neighbors(
                queries=[query_embedding],
                num_neighbors=n_results,
                filter=[
                    aiplatform.IndexDatapoint.Restriction(
                        namespace="user_id", allow_list=[user_id]
                    )
                ]
            )

            if not results or not results[0]:
                logging.info(f"No relevant entities found in vector store for user {user_id}.")
                return []

            neighbor_ids = [neighbor.id for neighbor in results[0]]
            logging.info(f"Vertex AI query for user {user_id} found {len(neighbor_ids)} relevant entity IDs.")
            return neighbor_ids

        except GoogleAPICallError as e:
            logging.error(f"Google API error during vector query for user {user_id}", exc_info=e)
            return []
        except Exception as e:
            logging.error(f"Failed to query Vertex AI for user {user_id}", exc_info=e)
            return []

    async def delete_entries(self, entry_ids: list[str]):
        """
        Deletes a list of datapoints from the index by their unique IDs.
        """
        if not entry_ids:
            return

        try:
            self.index_endpoint.remove_datapoints(datapoint_ids=entry_ids)
            logging.info(f"Successfully removed {len(entry_ids)} entries from the vector index.")
        except GoogleAPICallError as e:
            logging.error(f"Google API error while removing entries from vector index.", exc_info=e)
        except Exception as e:
            logging.error(f"Failed to remove entries from vector index.", exc_info=e)

