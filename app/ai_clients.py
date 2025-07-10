import os
import re
import time
import logging
from typing import List, Tuple
from xai_sdk import Client
from xai_sdk.chat import system, user, assistant

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class AIClient:
    """
    Abstract base class for AI clients.
    """
    def __init__(self, model: str = None, system_prompt: str = None):
        self.model = model
        self.system_prompt = system_prompt or (
            "You are an AI coding assistant in a Jupyter notebook. "
            "The conversation consists of user questions, additional user inputs, and executed code results (Jupyter outputs). "
            "Respond with Python code in a single ```python``` block and explanations outside the block."
        )

    def extract_code_and_clean_text(self, text: str) -> Tuple[str, str]:
        """
        Extracts the first Python code block and cleans the text.
        Returns: (code, cleaned_text)
        """
        match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
        if match:
            code = match.group(1)
            cleaned_text = text.replace(match.group(0), "").strip()
            return code, cleaned_text
        return None, text.strip()

    def query(self, history: List[dict]) -> Tuple[str, str, str]:
        """
        Queries the AI with conversation history.
        Returns: (original_response, code, text)
        """
        raise NotImplementedError()

    @staticmethod
    def validate_history(history: List[dict]):
        """
        Validates conversation history format.
        """
        for msg in history:
            if 'sender' not in msg or 'content' not in msg:
                raise ValueError(f"Invalid history message: {msg}")

    def map_history_to_agent(self, history: List[dict]) -> List[dict]:
        """
        Maps conversation history to xAI SDK compatible format.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        for msg in history:
            if msg['sender'] == 'user':
                messages.append({"role": "user", "content": msg['content']})
            elif msg['sender'] == 'assistant':
                messages.append({"role": "user", "content": f"Jupyter output:\n{msg['content']}"})
            elif msg['sender'] == 'system':
                continue
            else:
                raise ValueError(f"Unknown sender: {msg['sender']}")
        return messages

class GrokClient(AIClient):
    """
    Grok client using xAI Python SDK.
    """
    SUPPORTED_MODELS = ["grok-beta", "grok-2", "grok-3", "grok-3-latest"]

    def __init__(self, model: str = None, system_prompt: str = None):
        """
        Initializes the Grok client.
        """
        super().__init__(model, system_prompt)
        self.api_key = os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("XAI_API_KEY environment variable not set")

        self.model = model or "grok-3-latest"
        if self.model not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {self.model}")

        try:
            import xai_sdk
            logger.info(f"xAI SDK version: {xai_sdk.__version__}")
            self.client = Client(api_key=self.api_key)
            logger.info("Initialized xAI Client")
        except ImportError as e:
            logger.error("Failed to import xai_sdk: pip install xai-sdk")
            raise RuntimeError(f"xAI SDK import error: {str(e)}")

    def query(self, history: List[dict], max_retries: int = 3) -> Tuple[str, str, str]:
        """
        Queries the Grok API with retry logic.
        Returns: (original_response, code, text)
        """
        self.validate_history(history)
        messages = self.map_history_to_agent(history)
        logger.debug(f"Querying xAI API with messages: {messages}")

        for attempt in range(max_retries):
            try:
                chat = self.client.chat.create(model=self.model, temperature=0)
                logger.info(f"Started chat session with model {self.model}")

                for message in messages:
                    if message['role'] == 'system':
                        chat.append(system(message['content']))
                    elif message['role'] == 'user':
                        chat.append(user(message['content']))
                    elif message['role'] == 'assistant':
                        chat.append(assistant(message['content']))

                response = chat.sample()
                logger.info(f"Received response from xAI API")
                if hasattr(response, 'content'):
                    original = response.content.strip()
                    code, text = self.extract_code_and_clean_text(original)
                    return original, code, text
                else:
                    logger.warning("Response has no content attribute")
                    return "", None, ""
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Query failed after {max_retries} attempts: {str(e)}")
                time.sleep(2 ** attempt)  # Exponential backoff
        return "", None, ""

def get_client(name: str, model: str = None, system_prompt: str = None) -> AIClient:
    """
    Factory function to get AI client instance.
    """
    name = name.lower()
    if name == 'grok':
        return GrokClient(model, system_prompt)
    else:
        raise ValueError(f"Unknown AI client: {name}")