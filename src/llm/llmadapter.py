import src.config as conf
from openai import OpenAI
from src.llm.prompt import Prompt
import hashlib, json

class LLMAdapter():
    def __init__(self, model: str, read_from_cache: bool = False, save_to_cache: bool = False):
        self.read_from_cache = read_from_cache
        self.save_to_cache = save_to_cache
        if conf.llm['base']:
            self.client = OpenAI(base_url=conf.llm['base_url'], api_key=conf.llm['api_key'])
        else:
            self.client = OpenAI(api_key=conf.llm['api_key'])
        self.model = model
        self.cache_file = conf.llm['cache_file']
        self.cache = self._load_cache() # TODO: if exists

    def _make_cache_key(self, model: str, prompt: Prompt) -> str:
        key_data = {"model": model, "prompt": prompt}
        return hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

    def _cached_request(self, model: str, prompt: Prompt):
        #key = self._make_cache_key(model, prompt)
        #if key in self.cache:
        #    return self.cache[key]

        response = self._send_request(prompt)
        #self.cache[key] = response
        self._save_cache()
        return response
    
    # TODO: cache
    def _load_cache(self) -> dict:
        return {}
    
    def _save_cache(self) -> None:
        return

    def _send_request(self, prompt: Prompt):
        raise NotImplementedError

    def generate(self, prompt: Prompt) -> str:
        return self._cached_request(self.model, prompt)

    