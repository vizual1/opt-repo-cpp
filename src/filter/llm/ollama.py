import logging
from src.filter.llm.llmadapter import LLMAdapter
from src.filter.llm.prompt import Prompt
import requests

class OllamaLLM(LLMAdapter):
    def __init__(self, model: str):
        super().__init__(model)

    def _send_request(self, prompt: Prompt) -> str:
        full_prompt = "\n".join([m.content for m in prompt.messages]).strip()
        logging.info(f"LLM prompt: {full_prompt}")
        response = requests.post(f"http://localhost:11434/api/generate", json={
            "model": self.model,
            "prompt": full_prompt,
            "stream": False
        })
        return response.json()["response"]