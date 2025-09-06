import logging
import asyncio
import json
import google.generativeai as genai

# --- UPDATED IMPORTS ---
# GenerationConfig is imported directly.
from google.generativeai.types import GenerationConfig
# We import the 'types' module itself with a common alias 'glm' (Google Language Model).
import google.generativeai.types as glm


class LLMHandler:
    """Handles interactions with the Google Gemini model, including function calling."""

    def __init__(self, api_key, tool_handler, tool_schemas):
        """Configures the generative AI model with tools."""
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set.")

        genai.configure(api_key=api_key)
        self.tool_handler = tool_handler

        self.model = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config=GenerationConfig(
                temperature=0.8, top_p=0.95, top_k=40
            ),
            tools=tool_schemas
        )
        # Create a separate model instance specifically for JSON generation
        self.json_model = genai.GenerativeModel(
            'gemini-1.5-flash',
            generation_config=GenerationConfig(
                temperature=1.0  # Higher temperature for more creative generation
            )
        )
        logging.info("Generative AI models configured successfully.")

    async def generate_character_json(self, name, char_class, race, level, schema):
        """
        Uses the LLM to generate a character sheet as a JSON object.
        """
        logging.info(f"Generating character sheet for: {name} the {race} {char_class}")
        prompt = f"""
        Generate a complete D&D 5th Edition character sheet for a level {level} {race} {char_class} named {name}.
        The character sheet must be a valid JSON object that strictly adheres to the provided JSON schema.
        Please fill in all stats, skills, abilities, and a brief backstory appropriate for the character.
        Provide a reasonable starting inventory.
        """
        try:
            # The schema is passed along with the prompt to guide the model
            response = await self.json_model.generate_content_async(
                [prompt],
                generation_config=GenerationConfig(response_schema=schema)
            )
            sheet_json = json.loads(response.text)
            logging.info(f"Successfully generated JSON for character '{name}'.")
            return sheet_json
        except Exception as e:
            logging.error(f"Error generating character JSON for '{name}'", exc_info=e)
            return None

    async def generate_response(self, history):
        """
        Generates a response from the LLM. If the LLM requests a tool,
        this function executes the tool and sends the result back to the LLM
        to get the final, user-facing response.
        """
        try:
            chat_session = self.model.start_chat(history=history, enable_automatic_function_calling=False)
            user_prompt = history[-1]['parts'][0]

            response = await chat_session.send_message_async(user_prompt)
            response_part = response.parts[0]

            while response_part.function_call:
                function_call = response_part.function_call
                function_name = function_call.name
                function_args = dict(function_call.args)

                logging.info(f"LLM requested to call tool: '{function_name}' with arguments: {function_args}")

                if function_name in self.tool_handler.tools:
                    tool_function = self.tool_handler.tools[function_name]

                    if asyncio.iscoroutinefunction(tool_function):
                        function_response_data = await tool_function(**function_args)
                    else:
                        function_response_data = tool_function(**function_args)
                else:
                    logging.error(f"LLM tried to call a non-existent tool: {function_name}")
                    function_response_data = {"status": "error", "message": f"Tool '{function_name}' is not defined."}

                # --- UPDATED CODE to use the 'glm' alias ---
                # Send the tool's result back to the model using the new alias.
                response = await chat_session.send_message_async(
                    glm.Part(function_response=glm.FunctionResponse(
                        name=function_name,
                        response=function_response_data,
                    )
                    )
                )
                response_part = response.parts[0]

            final_response = response_part.text
            logging.info("Successfully generated final response from LLM.")
            return final_response

        except Exception as e:
            logging.error(f"An error occurred while generating the LLM response: {e}", exc_info=e)
            return "The world seems to shimmer and fade for a moment. I... I lost my train of thought. Can you repeat that?"

