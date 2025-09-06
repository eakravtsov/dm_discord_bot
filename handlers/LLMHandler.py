import google.generativeai as genai
import logging

class LLMHandler:
    """Handles interactions with the Google Gemini model."""

    def __init__(self, api_key):
        """Configures the generative AI model."""
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            'gemini-2.5-flash',
            generation_config=genai.GenerationConfig(
                temperature=0.8, top_p=0.95, top_k=40
            )
        )
        logging.info("Generative AI model configured successfully.")

    async def generate_response(self, history):
        """Generates a response from the LLM based on conversation history."""
        try:
            logging.info(f"Generating LLM response from history of length {len(history)}.")
            chat_session = self.model.start_chat(history=history)
            response = await chat_session.send_message_async(history[-1]['parts'][0])
            logging.info("LLM response generated successfully.")
            return response.text
        except Exception as e:
            logging.error(f"An error occurred while generating the LLM response: {e}", exc_info=e)
            return "The world seems to shimmer and fade for a moment. I... I lost my train of thought. Can you repeat that?"
