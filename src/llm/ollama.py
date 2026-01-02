from src.config.settings import LLMSettings
from src.llm.llmadapter import LLMAdapter
from src.llm.prompt import Prompt
import requests
from src.config.config import Config

class OllamaLLM(LLMAdapter):
    def __init__(self, config: Config, model: str):
        super().__init__(config, model)

    def _send_request(self, prompt: Prompt) -> str:
        full_prompt = "\n".join([m.content for m in prompt.messages]).strip()

        response = requests.post(self.config.llm.ollama_url, json={
            "model": self.model,
            "prompt": full_prompt,
            "stream": False
        })
        
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"Ollama error: {data['error']}")
        
        return response.json()["response"]