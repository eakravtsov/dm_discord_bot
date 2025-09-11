import google.generativeai as genai
import logging
import json
from google.generativeai.types import GenerationConfig


class LLMHandler:
    """Handles interactions with the Google Gemini models, including embeddings and world state extraction."""

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

        # Model for graph DB entity creation
        self.analyst_model = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config=GenerationConfig(temperature=0.2, response_mime_type="application/json")
        )

        # Model for vectorization
        self.embedding_model_name = 'models/text-embedding-004'
        logging.info("Generative AI models configured successfully.")

    async def generate_response(self, history, context: str = None):
        """Generates a response from the LLM based on conversation history and optional context."""
        try:
            logging.info(f"Generating LLM response from history of length {len(history)}.")
            last_user_message = history[-1]['parts'][0]

            prompt = last_user_message
            if context:
                prompt = f"Based on this relevant context:\n---\n{context}\n---\n The player says: {last_user_message}"

            response = await self.model.generate_content_async([*history[:-1], {'role': 'user', 'parts': [prompt]}])
            logging.info("LLM response generated successfully.")
            return response.text
        except Exception as e:
            logging.error("An error occurred while generating the LLM response.", exc_info=e)
            return "The world seems to shimmer and fade for a moment. I... I lost my train of thought. Can you repeat that?"

    async def generate_embedding(self, text: str) -> list[float]:
        """Generates a vector embedding for a given string of text."""
        try:
            result = await genai.embed_content_async(
                model=self.embedding_model_name,
                content=text
            )
            return result['embedding']
        except Exception as e:
            logging.error(f"Failed to generate embedding for text: '{text}'", exc_info=e)
            return []

    async def extract_world_state_from_history(self, history_to_analyze: list) -> list[dict]:
        """
        Analyzes a large chunk of conversation history and extracts a detailed,
        structured list of all significant entities (characters, locations, items).
        """
        logging.info(f"Extracting full world state from a history of {len(history_to_analyze)} entries.")

        formatted_history = "\n".join(
            f"{item['role'].capitalize()}: {item['parts'][0]}" for item in history_to_analyze
        )

        prompt = f"""
        You are a World Annalist. Your task is to meticulously analyze the following Dungeons & Dragons conversation log and extract all significant entities.

        Create a definitive list of every important Character, Location, and Item mentioned.
        - Consolidate information about a single entity from multiple mentions.
        - Infer relationships between entities (e.g., who is in what location, who owns what item).
        - Capture key properties like a character's disposition, species, or a location's description.
        - Ignore fleeting, unimportant details (e.g., a random dead goblin, a generic stream). Focus on entities that are named or have a clear role in the story.

        Format the output as a JSON object with a single key "entities" which contains a list of entity objects.
        Each entity object must have a "name", a "type" ('Character', 'Location', or 'Item'), and a "properties" dictionary.

        Example Conversation:
        User: I enter the tavern called The Gilded Mug. I ask the dwarf bartender, whose name is Blorf, for an ale.
        Model: Blorf the dwarf, a grumpy fellow, serves you a frothy ale. "That'll be two silver," he says, eyeing your sword. He mentions the tavern is in the city of Silverhaven.
        User: I give him the silver and ask about the Sword of Light.
        Model: Blorf scoffs. "A children's story," he says, polishing a glass. "You won't find that relic here."

        Desired JSON Output for Example:
        {{
          "entities": [
            {{
              "name": "The Gilded Mug",
              "type": "Location",
              "properties": {{
                "category": "Tavern",
                "location": "Silverhaven",
                "description": "A place where ale is served."
              }}
            }},
            {{
              "name": "Blorf",
              "type": "Character",
              "properties": {{
                "species": "Dwarf",
                "occupation": "Bartender",
                "workplace": "The Gilded Mug",
                "temperament": "Grumpy",
                "knowledge": "Knows the Sword of Light is considered a relic or story."
              }}
            }},
            {{
              "name": "Sword of Light",
              "type": "Item",
              "properties": {{
                "category": "Weapon",
                "rarity": "Relic",
                "status": "Considered a children's story by some."
              }}
            }}
          ]
        }}

        Now, analyze the following conversation and produce the JSON output:
        --- CONVERSATION LOG ---
        {formatted_history}
        --- END LOG ---
        """
        try:
            response = await self.analyst_model.generate_content_async(prompt)
            entity_data = json.loads(response.text)
            entities = entity_data.get("entities", [])

            if isinstance(entities, list):
                logging.info(f"Successfully extracted {len(entities)} entities from history chunk.")
                return entities
            else:
                logging.warning("LLM returned 'entities' but it was not a list.")
                return []
        except (json.JSONDecodeError, AttributeError) as e:
            logging.error(f"Failed to parse JSON world state from LLM response: {response.text}", exc_info=e)
            return []
        except Exception as e:
            logging.error("An error occurred during world state extraction.", exc_info=e)
            return []

    async def summarize_history(self, history_to_summarize: list) -> str:
        """
        Generates a prose summary of a conversation history chunk for the chat log.
        This is separate from the detailed world state extraction.
        """
        logging.info(f"Generating simple prose summary for a history of {len(history_to_summarize)} entries.")
        formatted_history = "\n".join(
            f"{item['role'].capitalize()}: {item['parts'][0]}" for item in history_to_summarize
        )

        prompt = f"""
        Please create a detailed narrative summary of the following Dungeons & Dragons session conversation as a list of key bulletpoints.
        This summary will be used as a reminder of the story so far for the player.

        Conversation:
        {formatted_history}
        """
        try:
            # Use the main conversational model for this simpler task
            response = await self.model.generate_content_async(prompt)
            summary_text = response.text.strip()
            logging.info("Successfully generated history summary.")
            return summary_text
        except Exception as e:
            logging.error("Failed to generate history summary.", exc_info=e)
            return "[Summary could not be generated due to an error.]"

