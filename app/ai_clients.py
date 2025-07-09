import os
import requests

class AIClient:
    """
    Abstract base class for AI clients.
    """
    def __init__(self, model=None):
        self.model = model

    def query(self, history):
        """
        Given conversation history (list of dicts with 'sender' and 'content'), return next code suggestion string.
        """
        raise NotImplementedError()


class OpenAIClient(AIClient):
    """
    OpenAI client using openai Python SDK.
    """
    def __init__(self, model=None):
        super().__init__(model)
        import openai
        self.openai = openai
        self.openai.api_key = os.getenv("OPENAI_API_KEY")
        if not self.model:
            self.model = "gpt-4"

    def query(self, history):
        messages = [
            {"role": "system", "content": "You are an AI that generates Python code based on the conversation."}
        ]

        # Convert our history to OpenAI chat roles
        for msg in history:
            if msg['sender'] == 'User':
                messages.append({"role": "user", "content": msg['content']})
            elif msg['sender'] == 'AI':
                messages.append({"role": "assistant", "content": msg['content']})
            elif msg['sender'] == 'Machine':
                # We can include machine output as user info or system info if needed
                messages.append({"role": "user", "content": f"Machine output:\n{msg['content']}"})
            elif msg['sender'] == 'System':
                messages.append({"role": "system", "content": msg['content']})

        response = self.openai.ChatCompletion.create(
            model=self.model,
            messages=messages,
            temperature=0
        )
        return response.choices[0].message.content.strip()


class ClaudeClient(AIClient):
    """
    Anthropic Claude client using anthropic Python SDK.
    """
    def __init__(self, model=None):
        super().__init__(model)
        import anthropic
        self.anthropic = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        if not self.model:
            self.model = "claude-3-opus-20240229"

    def query(self, history):
        prompt_parts = []
        for msg in history:
            if msg['sender'] == 'User':
                prompt_parts.append(f"\n\nHuman: {msg['content']}")
            elif msg['sender'] == 'AI':
                prompt_parts.append(f"\n\nAssistant: {msg['content']}")
            elif msg['sender'] == 'Machine':
                prompt_parts.append(f"\n\nMachine: {msg['content']}")
            elif msg['sender'] == 'System':
                prompt_parts.append(f"\n\nSystem: {msg['content']}")

        prompt = "".join(prompt_parts) + "\n\nAssistant:"

        response = self.anthropic.completions.create(
            model=self.model,
            max_tokens_to_sample=1024,
            prompt=prompt,
            stop_sequences=["\n\nHuman:"]
        )
        return response.completion.strip()


class GrokClient(AIClient):
    """
    Grok client using REST API.
    """
    def __init__(self, model=None):
        super().__init__(model)
        self.api_key = os.getenv("GROK_API_KEY")
        self.base_url = os.getenv("GROK_API_BASE_URL", "https://api.x.ai/v1")
        if not self.api_key:
            raise RuntimeError("GROK_API_KEY environment variable not set")
        if not self.model:
            self.model = "grok-1"

    def query(self, history):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = [
            {"role": "system", "content": "You are an AI that generates Python code based on the conversation."}
        ]

        for msg in history:
            if msg['sender'] == 'User':
                messages.append({"role": "user", "content": msg['content']})
            elif msg['sender'] == 'AI':
                messages.append({"role": "assistant", "content": msg['content']})
            elif msg['sender'] == 'Machine':
                messages.append({"role": "user", "content": f"Machine output:\n{msg['content']}"})
            elif msg['sender'] == 'System':
                messages.append({"role": "system", "content": msg['content']})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0
        }

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content'].strip()


def get_client(name, model):
    name = name.lower()
    if name == 'openai':
        return OpenAIClient(model)
    elif name == 'claude':
        return ClaudeClient(model)
    elif name == 'grok':
        return GrokClient(model)
    else:
        raise ValueError(f"Unknown AI client: {name}")
