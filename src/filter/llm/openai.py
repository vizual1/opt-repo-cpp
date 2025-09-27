from src.filter.llm.llmadapter import LLMAdapter 
from src.filter.llm.prompt import Prompt

class OpenRouterLLM(LLMAdapter):
    def __init__(self, model: str):
        super().__init__(model)

    def _send_request(self, prompt: Prompt):
        completion = self.client.chat.completions.create(
            model=f"{self.model}",
            messages=[m.__dict__ for m in prompt.messages] # type: ignore
        )
        #response.raise_for_status()
        return completion.choices[0].message.content #response.json()["choices"][0]["message"]["content"]
        