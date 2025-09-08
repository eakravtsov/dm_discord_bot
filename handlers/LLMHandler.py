import google.generativeai as genai
import logging
import json
from google.generativeai.types import GenerationConfig


class LLMHandler:
    """Handles interactions with the Google Gemini models, including embeddings."""

    def __init__(self, api_key):
        """Configures the generative AI models."""
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set.")
        genai.configure(api_key=api_key)

        # Main model for conversational turns
        self.model = genai.GenerativeModel(
            'gemini-2.5-flash',
            generation_config=GenerationConfig(temperature=0.8, top_p=0.95, top_k=40)
        )

        # A separate model instance for tasks requiring structured output (JSON)
        self.summarizer_model = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config=GenerationConfig(temperature=0.2, response_mime_type="application/json")
        )

        self.history_model = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config=GenerationConfig(temperature=0.5)
        )

        # The model name for embeddings is specified directly in the API call
        self.embedding_model_name = 'models/text-embedding-004'

        logging.info("Generative AI models configured successfully.")

    async def generate_response(self, history: list, context: str = None):
        """
        Generates a response from the LLM based on conversation history and optional context.
        This method is now stateless and does not use a chat_session object.
        """
        try:
            logging.info(f"Generating LLM response from history of length {len(history)}.")

            # The full history is passed directly to the model.
            # We augment the last user message with our RAG context.
            contents = list(history)
            if context:
                # Prepend the context to the last user message for maximum relevance.
                contents[-1]['parts'][0] = f"CONTEXT:\n{context}\n\nPLAYER:\n{contents[-1]['parts'][0]}"

            response = await self.model.generate_content_async(contents)
            logging.info("LLM response generated successfully.")
            return response.text
        except Exception as e:
            logging.error("An error occurred while generating the LLM response.", exc_info=e)
            return "The world seems to shimmer and fade... I lost my train of thought. Can you repeat that?"

    async def generate_embedding(self, text: str) -> list[float]:
        """Generates a vector embedding for a given string of text."""
        try:
            result = await genai.embed_content_async(model=self.embedding_model_name, content=text)
            return result['embedding']
        except Exception as e:
            logging.error(f"Failed to generate embedding for text: '{text}'", exc_info=e)
            return []

    async def extract_facts(self, conversation_chunk: str) -> list[dict]:
        """Extracts key entities and their properties from a conversation chunk."""
        prompt = f"""
        Analyze the following Dungeons & Dragons conversation snippet.
        Identify all key entities (characters, locations, items, concepts).
        For each entity, extract its type, name, and any properties or relationships with other entities.
        Format the output as a JSON object with a single key "entities" containing a list of these structured entity objects.
        An entity must have "name" and "type". "properties" are optional.

        Example:
        - Player: I enter the tavern called The Gilded Mug. I ask the dwarf bartender, Blorf, for an ale.
        - DM: Blorf grunts and serves you a frothy ale. "That'll be two silver," he says.

        Output for example:
        {{
            "entities": [
                {{"name": "The Gilded Mug", "type": "Location", "properties": {{"category": "Tavern"}}}},
                {{"name": "Blorf", "type": "Character", "properties": {{"species": "Dwarf", "occupation": "Bartender", "workplace": "The Gilded Mug"}}}},
                {{"name": "Ale", "type": "Item", "properties": {{"cost": "2 silver pieces", "sold_at": "The Gilded Mug"}}}}
            ]
        }}

        Conversation to analyze:
        {conversation_chunk}
        """
        try:
            logging.info("Extracting structured entities from conversation chunk.")
            response = await self.summarizer_model.generate_content_async(prompt)
            data = json.loads(response.text)
            entities = data.get("entities", [])
            if isinstance(entities, list):
                logging.info(f"Successfully extracted {len(entities)} entities.")
                return entities
            return []
        except (json.JSONDecodeError, AttributeError, Exception) as e:
            logging.error("An error occurred during entity extraction.", exc_info=e)
            return []

    async def summarize_history(self, history_to_summarize):
        """Generates a concise summary of a provided conversation history chunk."""
        logging.info(f"Summarizing a chunk of history with {len(history_to_summarize)} entries.")
        formatted_history = "\n".join(
            f"{item['role'].capitalize()}: {item['parts'][0]}" for item in history_to_summarize
        )
        prompt = f"""
        Please summarize the following Dungeons & Dragons session conversation. 
        Capture the key events, decisions, and outcomes as a list of bulletpoints.
        This summary will be used as context for the continuation of the game.

        Conversation:
        {formatted_history}
        """
        try:
            response = await self.history_model.generate_content_async(prompt)
            return response.text.strip()
        except Exception as e:
            logging.error("Failed to generate history summary.", exc_info=e)
            return "[Summary could not be generated due to an error.]"

