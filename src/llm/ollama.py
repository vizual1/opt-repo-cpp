from src.llm.llmadapter import LLMAdapter
from src.llm.prompt import Prompt
import requests
import src.config as conf

class OllamaLLM(LLMAdapter):
    def __init__(self, model: str):
        super().__init__(model)

    def _send_request(self, prompt: Prompt) -> str:
        full_prompt = "\n".join([m.content for m in prompt.messages]).strip()
        response = requests.post(conf.llm['ollama_url'], json={
            "model": self.model,
            "prompt": full_prompt,
            "stream": False
        })
        return response.json()["response"]