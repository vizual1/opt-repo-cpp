from src.filter.llm.llmadapter import LLMAdapter 
from src.filter.llm.prompt import Prompt
from typing import Union

class OpenRouterLLM(LLMAdapter):
    def __init__(self, model: str):
        super().__init__(model)

    def _send_request(self, prompt: Prompt) -> Union[str, None]:
        completion = self.client.chat.completions.create(
            model=f"{self.model}",
            messages=[m.__dict__ for m in prompt.messages] # type: ignore
        )
        return completion.choices[0].message.content
        