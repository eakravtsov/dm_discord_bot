import logging
from neo4j import AsyncGraphDatabase


class GraphHandler:
    """Manages all interactions with the Neo4j graph database."""

    def __init__(self, uri, user, password):
        """Initializes the connection to the Neo4j database."""
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        logging.info("Neo4j driver initialized.")

    async def close(self):
        """Closes the database driver connection."""
        await self.driver.close()
        logging.info("Neo4j driver closed.")

    async def get_entity_context(self, user_id: str, entity_name: str) -> str:
        """
        Retrieves an entity and its direct relationships to form a context string.

        Args:
            user_id: The Discord user ID to scope the search.
            entity_name: The name of the central entity to query.

        Returns:
            A formatted string describing the entity and its connections,
            or an empty string if the entity is not found.
        """
        logging.info(f"Querying graph context for entity '{entity_name}' for user {user_id}.")
        async with self.driver.session() as session:
            # This Cypher query finds the starting node (n) and then optionally matches
            # all nodes (m) that are connected to it by any relationship (r).
            result = await session.run(
                """
                MATCH (n {name: $name, userId: $userId})
                OPTIONAL MATCH (n)-[r]-(m)
                RETURN n, type(r) as rel_type, m
                """,
                name=entity_name,
                userId=user_id
            )

            records = await result.data()
            if not records:
                return ""

            # The first record contains the properties of the main entity itself.
            main_node = records[0]['n']
            main_node_type = list(main_node.labels)[0]
            context_lines = [
                f"Here is what is known about {main_node['name']} (a {main_node_type}):"
            ]

            # Add properties of the main node
            for key, value in main_node.items():
                if key not in ['name', 'userId']:
                    context_lines.append(f"- {main_node['name']}'s {key} is {value}.")

            # Add relationships
            for record in records:
                if record['rel_type'] and record['m']:
                    rel_type = record['rel_type'].replace('_', ' ').lower()
                    target_node = record['m']
                    context_lines.append(f"- {main_node['name']} {rel_type} {target_node['name']}.")

            return "\n".join(context_lines)

    async def add_or_update_entity(self, user_id: str, entity: dict):
        """
        Adds or updates an entity in the graph, creating nodes and relationships.
        This function is idempotent: running it multiple times has no negative effect.

        Args:
            user_id: The Discord user ID to scope the data.
            entity: A dictionary representing the entity, from LLMHandler.
        """
        entity_name = entity.get("name")
        entity_type = entity.get("type", "Thing")  # Default type if not specified
        properties = entity.get("properties", {})

        if not entity_name:
            logging.warning(f"Skipping entity with no name: {entity}")
            return

        async with self.driver.session() as session:
            # Step 1: Create or find the main entity node.
            # MERGE finds a node with the given properties or creates it if it doesn't exist.
            # We scope entities by user_id to keep player worlds separate.
            await session.run(
                """
                MERGE (n:%s {name: $name, userId: $userId})
                ON CREATE SET n += $props
                ON MATCH SET n += $props
                """ % entity_type,  # Safely inject the label using %
                name=entity_name,
                userId=user_id,
                props=properties
            )

            # Step 2: Iterate through properties to create relationship links.
            for key, value in properties.items():
                # A simple heuristic: if a property value matches the name of another known entity type,
                # we assume it's a relationship. This can be made more sophisticated later.
                # Example: {"workplace": "The Gilded Mug"}

                # Check if the value could be a node itself
                # For now, let's assume if it's a string, we can try to link it.
                if isinstance(value, str):
                    await session.run(
                        """
                        // Find the source node (e.g., Blorf)
                        MATCH (source:%s {name: $source_name, userId: $userId})
                        // Find or create the target node (e.g., The Gilded Mug)
                        MERGE (target {name: $target_name, userId: $userId})
                        // Create a relationship between them
                        MERGE (source)-[:%s]->(target)
                        """ % (entity_type, key.upper()),  # e.g., Blorf, WORKS_AT
                        source_name=entity_name,
                        target_name=value,
                        userId=user_id
                    )

            logging.info(f"Upserted entity '{entity_name}' for user {user_id}.")

