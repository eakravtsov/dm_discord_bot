import logging
import uuid
from typing import Optional

from neo4j import AsyncGraphDatabase

class GraphHandler:
    """Manages all interactions with the Neo4j graph database."""

    def __init__(self, uri, user, password):
        """Initializes the Neo4j driver."""
        try:
            self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
            logging.info("Neo4j driver initialized successfully.")
        except Exception as e:
            logging.error("Failed to initialize Neo4j driver.", exc_info=e)
            self.driver = None

    async def close(self):
        """Closes the connection to the database."""
        if self.driver:
            await self.driver.close()
            logging.info("Neo4j driver closed.")

    async def add_or_update_entity(self, user_id: str, entity: dict) -> str:
        """
        Creates or updates an entity node and its properties in the graph for a specific user.
        This operation is idempotent. It also creates relationships based on properties.
        Returns the unique ID of the node.
        """
        if not self.driver:
            return None

        entity_name = entity.get("name")
        entity_type = entity.get("type", "Thing")
        properties = entity.get("properties", {})

        # Assign a unique ID if one doesn't exist for relationship linking
        node_id = str(uuid.uuid4())

        async with self.driver.session() as session:
            # MERGE finds a node or creates it if it doesn't exist.
            # We match on both name and userId to ensure data is scoped per user.
            query = (
                    "MERGE (n:%s {name: $name, userId: $userId}) "
                    "ON CREATE SET n.nodeId = $nodeId, n += $props "
                    "ON MATCH SET n += $props "
                    "RETURN n.nodeId as nodeId" % entity_type  # Safely inject entity type
            )

            result = await session.run(query, name=entity_name, userId=user_id, nodeId=node_id, props=properties)
            record = await result.single()
            created_node_id = record["nodeId"]

            # Create relationships
            for key, value in properties.items():
                if isinstance(value, str):  # Simple relationship check
                    # Try to link to another entity node owned by the same user
                    rel_query = (
                            "MATCH (a {name: $a_name, userId: $userId}), (b {name: $b_name, userId: $userId}) "
                            "MERGE (a)-[:%s]->(b)" % key.upper()  # Relationship type from property key
                    )
                    await session.run(rel_query, a_name=entity_name, b_name=value, userId=user_id)

            return created_node_id

    async def get_all_user_node_ids(self, user_id: str) -> list[str]:
        """Retrieves all node UUIDs for a given user, used for deletion."""
        if not self.driver:
            return []

        async with self.driver.session() as session:
            query = "MATCH (n {userId: $userId}) WHERE n.nodeId IS NOT NULL RETURN n.nodeId as nodeId"
            result = await session.run(query, userId=user_id)
            return [record["nodeId"] async for record in result]

    async def delete_user_data(self, user_id: str):
        """Deletes all nodes and relationships associated with a user."""
        if not self.driver:
            return

        async with self.driver.session() as session:
            query = "MATCH (n {userId: $userId}) DETACH DELETE n"
            await session.run(query, userId=user_id)
            logging.info(f"Deleted all graph data for user {user_id}.")

    async def get_entity_context(self, user_id: str, node_id: str) -> Optional[str]:
        """Retrieves a formatted string describing an entity and its direct relationships."""
        if not self.driver:
            return None

        async with self.driver.session() as session:
            query = (
                "MATCH (n {nodeId: $nodeId, userId: $userId}) "
                "OPTIONAL MATCH (n)-[r]-(m) "
                "RETURN n, r, m"
            )
            result = await session.run(query, nodeId=node_id, userId=user_id)
            records = await result.list()

            if not records:
                return None

            main_node = records[0]["n"]
            node_type = list(main_node.labels)[0]
            context = f"Here is what is known about {main_node['name']} (a {node_type}):\n"

            props = []
            for key, value in main_node.items():
                if key not in ["name", "userId", "nodeId"]:
                    props.append(f"- {main_node['name']}'s {key} is {value}.")

            for record in records:
                if record["r"] and record["m"]:
                    rel_type = record["r"].type.replace("_", " ").lower()
                    related_node = record["m"]
                    props.append(f"- {main_node['name']} {rel_type} {related_node['name']}.")

            return context + "\n".join(props)
