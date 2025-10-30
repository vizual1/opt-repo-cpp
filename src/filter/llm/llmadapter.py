import src.config as conf
from openai import OpenAI
from src.filter.llm.prompt import Prompt

class LLMAdapter():
    def __init__(self, model: str, read_from_cache: bool = False, save_to_cache: bool = False):
        self.read_from_cache = read_from_cache
        self.save_to_cache = save_to_cache
        if conf.llm['base']:
            self.client = OpenAI(base_url=conf.llm['base_url'], api_key=conf.llm['api_key'])
        else:
            self.client = OpenAI(api_key=conf.llm['api_key'])
        self.model = model

    def _send_request(self, prompt: Prompt):
        raise NotImplementedError

    def generate(self, prompt: Prompt) -> str:
        return self._send_request(prompt)

    