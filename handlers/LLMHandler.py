import google.generativeai as genai
import logging

class LLMHandler:
    """Handles interactions with the Google Gemini model."""

    def __init__(self, api_key):
        """Configures the generative AI model."""
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set.")
        genai.configure(api_key=api_key)

        # Main model for conversational turns
        self.model = genai.GenerativeModel('gemini-2.5-flash',  generation_config=genai.GenerationConfig(
                temperature=0.8, top_p=0.95, top_k=40
            ))

        # A separate, simple model instance for summarization tasks
        self.summarizer_model = genai.GenerativeModel('gemini-2.5-flash', generation_config=genai.GenerationConfig(
                temperature=0.8, top_p=0.95, top_k=40
            ))

        logging.info("Generative AI models configured successfully.")

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

    async def summarize_history(self, history_to_summarize):
        """
        Generates a concise summary of a provided conversation history chunk.
        """
        logging.info(f"Summarizing a chunk of history with {len(history_to_summarize)} entries.")

        # Convert the list of dictionaries into a simple, readable string format.
        formatted_history = "\n".join(
            f"{item['role'].capitalize()}: {item['parts'][0]}" for item in history_to_summarize
        )

        prompt = f"""
        Please summarize the following Dungeons & Dragons session conversation. 
        Capture the key events, decisions, and outcomes in a concise narrative paragraph. 
        This summary will be used as context for the continuation of the game.

        Conversation:
        {formatted_history}
        """
        try:
            response = await self.summarizer_model.generate_content_async(prompt)
            summary_text = response.text.strip()
            logging.info("Successfully generated history summary.")
            return summary_text
        except Exception as e:
            logging.error("Failed to generate history summary.", exc_info=e)
            return "[Summary could not be generated due to an error.]"

