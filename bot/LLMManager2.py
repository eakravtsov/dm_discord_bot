import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.messages import SystemMessage, HumanMessage

class ChatLlmManager:
    def __init__(self):
        model_id = "mistralai/Mistral-7B-Instruct-v0.2"
        load_dotenv()
        api_token = os.getenv("HUGGING_FACE_TOKEN")
        if not api_token:
            raise ValueError("HUGGING_FACE_TOKEN not set. Obtain one from Hugging Face settings.")

        print(f"Initializing remote LLM endpoint for model: {model_id}")
        llm = HuggingFaceEndpoint(
            repo_id=model_id,
            huggingfacehub_api_token=api_token,
            max_new_tokens=250,
            temperature=0.7,
        )

        # Wrap it into a chat interface
        self.chat = ChatHuggingFace(llm=llm, verbose=False)

        # Optional: Start with a system prompt
        self.system_message = SystemMessage(content="You are a creative Dungeon Master for D&D 5e.")
        self.history = []

        print("✅ ChatLlmManager initialized with ChatHuggingFace!")

    def get_response(self, user_input: str) -> str:
        messages = [self.system_message] + self.history + [HumanMessage(content=user_input)]
        ai_response = self.chat.invoke(messages)
        assistant_content = ai_response.content
        self.history.append(HumanMessage(content=user_input))
        self.history.append(ai_response)
        print(f"User: {user_input}")
        print(f"Assistant: {assistant_content}")
        return assistant_content


if __name__ == '__main__':
    # Create an instance of the manager
    # This will fail if the environment variable is not set
    try:
        llm_manager = ChatLlmManager()

        # Define a sample prompt
        prompt = "What do I see up ahead?"

        # Get the response
        response = llm_manager.get_response(prompt)

        # Print the final result
        print("\n--- Final Answer ---")
        print(f"Question: {prompt}")
        print(f"Answer: {response}")
        print("--------------------")

    except ValueError as e:
        print(f"🛑 ERROR: {e}")