import os
import requests

import os
from xai_sdk import Client
import time
import random

import os
import time
import random
import logging
from xai_sdk import Client

import re
import os
import time
import random
import logging
from xai_sdk import Client
from xai_sdk.chat import system, user, assistant

# Configure logging for debugging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class AIClient:
    """
    Abstract base class for AI clients.
    """
    def __init__(self, model=None, system_prompt=None):
        self.model = model
        self.system_prompt = system_prompt or (
            "You are an AI coding assistant in a Jupyter notebook. "
            "The conversation consists of user questions and executed code results (Jupyter outputs). "
            "You respond with Python code and explanations when appropriate."
        )

    def extract_code_and_clean_text(self, text):
        """
        Extracts the first Python code block from markdown-style content.
        Returns a tuple:
        (code inside the block, text without the code block including delimiters)
        """
        # Regex to find the code block including delimiters
        match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
        if match:
            code_only = match.group(1)             # Extract inner code
            full_block = match.group(0)            # Entire block with backticks
            cleaned_text = text.replace(full_block, "").strip()  # Remove block completely
            return code_only, cleaned_text
        return None, text.strip()

    def query(self, history):
        """
        Given conversation history (list of dicts with 'sender' and 'content'), return next code suggestion string.
        Only considers User and Jupyter messages as input.
        """
        raise NotImplementedError()

    @staticmethod
    def validate_history(history):
        for msg in history:
            if 'sender' not in msg or 'content' not in msg:
                raise ValueError(f"Invalid history message: {msg}")

    def map_history_to_agent(self, history):
        """
        Maps conversation history to OpenAI / Grok compatible message format.
        Filters out AI responses from history.
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

# Configure logging for debugging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class GrokClient(AIClient):
    """
    Grok client using the official xAI Python SDK (synchronous, non-streaming).
    Uses chat.create and sample() to generate a parsed response.
    """
    SUPPORTED_MODELS = ["grok-beta", "grok-2", "grok-3", "grok-3-latest"]

    def __init__(self, model=None, system_prompt=None):
        """
        Initialize the Grok client with synchronous xAI SDK client.

        Args:
            model (str, optional): The Grok model to use (e.g., 'grok-3-latest').
            system_prompt (str, optional): Custom system prompt.
        """
        super().__init__(model, system_prompt)
        self.api_key = os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("XAI_API_KEY environment variable not set")

        # Set default model to grok-3-latest to match cURL example
        self.model = model or "grok-3-latest"
        if self.model not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {self.model}. Supported models: {self.SUPPORTED_MODELS}")

        # Initialize xAI SDK client
        try:
            import xai_sdk
            logger.info(f"xAI SDK version: {xai_sdk.__version__}")
            self.client = Client(api_key=self.api_key)
            logger.info("Initialized xAI Client")
            # Verify chat.create exists
            if not hasattr(self.client.chat, 'create'):
                logger.error("Client.chat does not have 'create' attribute. Available attributes: %s", dir(self.client.chat))
                raise RuntimeError("xAI SDK Client.chat is missing 'create'. Check SDK version.")
        except ImportError as e:
            logger.error("Failed to import xai_sdk. Ensure it is installed: pip install xai-sdk")
            raise RuntimeError(f"xAI SDK import error: {str(e)}")

    def query(self, history, max_retries=3):
        """
        Query the Grok API with conversation history and return the parsed response.

        Args:
            history (list): List of message dictionaries with 'sender' and 'content'.
            max_retries (int): Maximum number of retry attempts for rate limit errors.

        Returns:
            str: The parsed API response content.

        Raises:
            RuntimeError: If the query fails after retries or due to other errors.
        """
        self.validate_history(history)
        messages = self.map_history_to_agent(history)
        logger.debug(f"Querying xAI API with messages: {messages}")

        for attempt in range(max_retries):
            try:
                # Create chat session
                chat = self.client.chat.create(
                    model=self.model,
                    temperature=0
                )
                logger.info(f"Started chat session with xAI API for model {self.model}")

                # Append messages to chat
                for message in messages:
                    if message['role'] == 'system':
                        chat.append(system(message['content']))
                    elif message['role'] == 'user':
                        chat.append(user(message['content']))
                    elif message['role'] == 'assistant':
                        chat.append(assistant(message['content']))
                    else:
                        logger.warning(f"Skipping unsupported message role: {message['role']}")

                # Get response
                response = chat.sample()
                logger.info(f"Received response from xAI API for model {self.model}")
                if hasattr(response, 'content'):
                    original = response.content.strip()
                    code, text = self.extract_code_and_clean_text(original)
                    return original, code, text
                else:
                    logger.warning("Response has no content attribute: %s", vars(response) if hasattr(response, '__dict__') else str(response))
                    return ""
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                raise RuntimeError(f"Unexpected error: {str(e)}")

def get_client(name, model=None, system_prompt=None):
    name = name.lower()
    return GrokClient(model, system_prompt)

    if name == 'openai':
        return OpenAIClient(model, system_prompt)
    elif name == 'claude':
        return ClaudeClient(model, system_prompt)
    elif name == 'grok':
        return GrokClient(model, system_prompt)
    else:
        raise ValueError(f"Unknown AI client: {name}")
