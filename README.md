<h1>AI Dungeon Master Discord Bot</h1>

<h2>Overview</h2>
This project is an advanced, AI-powered Dungeon Master bot for Discord, designed to create persistent, dynamic, and immersive Dungeons & Dragons (5th Edition) campaigns. Unlike simple chatbots, this DM possesses a sophisticated long-term memory, allowing it to build a unique and consistent world for each group of players.

The bot leverages the latest Large Language Models (LLMs), such as Google's Gemini 2.5, to generate creative narrative, roleplay as non-player characters (NPCs), and respond dynamically to player actions.

<h3>Core Functionality & Architecture</h3>
The bot's intelligence is powered by a hybrid memory system built on a Retrieval-Augmented Generation (RAG) architecture. This ensures that the LLM's responses are not only creative but also deeply rooted in the established lore of the ongoing campaign.

This "brain" consists of two main components:

**Graph Database** (Neo4j): The "source of truth" for the game world. A Graph Database is used to store structured data about all significant entities—characters, locations, items—and the complex relationships between them. This allows the bot to answer relational queries and maintain a consistent world state (e.g., knowing which characters are in a specific tavern).

**Vector Database** (ChromaDB): The "search index" for semantic understanding. A Vector Database stores numerical representations (embeddings) of the world's lore. When a player sends a message, this database enables powerful semantic search, allowing the bot to find the most contextually relevant entities from the graph, even if the player's wording is vague or indirect.

<h3>Optimized Memory Consolidation</h3>
To ensure the quality of its long-term memory, the bot does not update its knowledge base on every message. Instead, it performs a periodic world-state consolidation. Every 100 messages, the LLM analyzes the recent conversation in-depth, extracts a clean and high-quality summary of all significant new entities and relationships, and then updates the Graph and Vector Databases in a single, intelligent batch operation.

<h3>Interactive Experience</h3>
Leveraging the Discord client allows the bot to embed context-appropriate UI elements - for example, a "roll dice" button when the DM prompts for a roll.