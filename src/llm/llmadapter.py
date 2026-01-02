from openai import OpenAI
from src.llm.prompt import Prompt
from src.config.config import Config

class LLMAdapter():
    def __init__(self, config: Config, model: str, read_from_cache: bool = False, save_to_cache: bool = False):
        self.config = config
        self.read_from_cache = read_from_cache
        self.save_to_cache = save_to_cache
        if self.config.llm.base:
            self.client = OpenAI(base_url=self.config.llm.base_url, api_key=self.config.llm.api_key)
        else:
            self.client = OpenAI(api_key=self.config.llm.api_key)
        self.model = model

    def _send_request(self, prompt: Prompt):
        raise NotImplementedError

    def generate(self, prompt: Prompt) -> str:
        return self._send_request(prompt)

    