import os
import re
import logging
from typing import Tuple, Optional, List, Dict
from xai_sdk import Client
from xai_sdk.chat import system, user, assistant

logger = logging.getLogger(__name__)

class AIClient:
    """Abstract base class for AI clients with enhanced error handling and logging."""
    
    def __init__(self, model: Optional[str] = None, system_prompt: Optional[str] = None):
        self.model = model
        self.system_prompt = system_prompt or (
            "You are an expert AI coding assistant. Your responses should include:\n"
            "1. Clear explanations of the solution approach\n"
            "2. Well-formatted Python code blocks when applicable\n"
            "3. Analysis of potential edge cases\n"
            "4. Suggestions for optimization and improvement"
        )
        self._validate_initialization()

    def _validate_initialization(self):
        """Validate that required configurations are present."""
        if not self.model:
            raise ValueError("Model name must be specified")
        if not self.system_prompt:
            raise ValueError("System prompt must be specified")

    def extract_code_and_clean_text(self, text: str) -> Tuple[Optional[str], str]:
        """
        Enhanced code extraction with support for multiple code blocks.
        Returns:
            Tuple: (combined_code, cleaned_text)
        """
        code_blocks = []
        cleaned_text = text
        
        # Find all Python code blocks
        pattern = r"```python\n(.*?)\n```"
        matches = re.finditer(pattern, text, re.DOTALL)
        
        for match in matches:
            code_blocks.append(match.group(1))
            cleaned_text = cleaned_text.replace(match.group(0), "")
        
        combined_code = "\n\n# ----- New Code Block -----\n\n".join(code_blocks) if code_blocks else None
        return combined_code, cleaned_text.strip()

    def query(self, history: List[Dict[str, str]]) -> Tuple[str, Optional[str], str]:
        """
        Enhanced query method with better error handling and validation.
        Returns:
            Tuple: (original_response, extracted_code, cleaned_text)
        """
        self._validate_history(history)
        messages = self._prepare_messages(history)
        return self._execute_query(messages)

    def _validate_history(self, history: List[Dict[str, str]]):
        """Validate conversation history structure."""
        if not isinstance(history, list):
            raise ValueError("History must be a list")
        
        for msg in history:
            if not isinstance(msg, dict):
                raise ValueError("Each message must be a dictionary")
            if 'sender' not in msg or 'content' not in msg:
                raise ValueError("Each message must have 'sender' and 'content' keys")
            if not isinstance(msg['content'], str):
                raise ValueError("Message content must be a string")

    def _prepare_messages(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Prepare messages in the format expected by the AI model."""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        for msg in history:
            role = "user" if msg['sender'] == 'user' else "assistant"
            content = msg['content']
            
            if msg['sender'] == 'assistant':
                content = f"Execution Result:\n{content}"
            
            messages.append({"role": role, "content": content})
        
        return messages

    def _execute_query(self, messages: List[Dict[str, str]]) -> Tuple[str, Optional[str], str]:
        """Execute the query against the AI model (to be implemented by subclasses)."""
        raise NotImplementedError("Subclasses must implement this method")


class GrokClient(AIClient):
    """Enhanced Grok client with better error handling and retry logic."""
    
    SUPPORTED_MODELS = ["grok-beta", "grok-2", "grok-3", "grok-3-latest"]
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # seconds

    def __init__(self, model: Optional[str] = None, system_prompt: Optional[str] = None):
        super().__init__(model, system_prompt)
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Grok client with proper configuration."""
        self.api_key = os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("XAI_API_KEY environment variable not set")

        self.model = self.model or "grok-3-latest"
        if self.model not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {self.model}. Supported: {', '.join(self.SUPPORTED_MODELS)}")

        try:
            self.client = Client(api_key=self.api_key)
            logger.info("Successfully initialized Grok client for model %s", self.model)
        except Exception as e:
            logger.error("Failed to initialize Grok client: %s", str(e))
            raise RuntimeError(f"Failed to initialize Grok client: {str(e)}")

    def _execute_query(self, messages: List[Dict[str, str]]) -> Tuple[str, Optional[str], str]:
        """Execute query with retry logic and enhanced error handling."""
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                chat = self.client.chat.create(model=self.model, temperature=0.7)
                
                # Add messages to chat
                for msg in messages:
                    if msg['role'] == 'system':
                        chat.append(system(msg['content']))
                    elif msg['role'] == 'user':
                        chat.append(user(msg['content']))
                    elif msg['role'] == 'assistant':
                        chat.append(assistant(msg['content']))
                
                # Get response
                response = chat.sample()
                
                if hasattr(response, 'content'):
                    original = response.content.strip()
                    code, text = self.extract_code_and_clean_text(original)
                    return original, code, text
                else:
                    logger.warning("Unexpected response format from Grok API")
                    return "No response content received", None, "No response content received"
            
            except Exception as e:
                last_error = e
                logger.warning("Attempt %d failed: %s", attempt + 1, str(e))
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        logger.error("All %d attempts failed. Last error: %s", self.MAX_RETRIES, str(last_error))
        raise RuntimeError(f"Failed after {self.MAX_RETRIES} attempts. Last error: {str(last_error)}")


def get_client(name: str, model: Optional[str] = None, system_prompt: Optional[str] = None) -> AIClient:
    """Factory function to get the appropriate AI client."""
    name = name.lower()
    
    if name == 'grok':
        return GrokClient(model, system_prompt)
    # Add other clients here as needed
    else:
        raise ValueError(f"Unsupported AI client: {name}")