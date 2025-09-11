import os
from typing import Any

storage: dict[str, str] = {
    "dataset": "data",
    "repo_urls": "data/repo_urls.txt",
    "history": "history.txt",
    "filtered": "filtered.txt",
    "results": "results.txt"
}

llm: dict[str, Any] = {
    'cache_file': 'test',
    'api_key': os.environ['api_key'],
    'base': True,
    'base_url': 'https://openrouter.ai/api/v1',
    'model': 'z-ai/glm-4.5-air:free'
}
# openai/gpt-oss-120b:free

github: dict[str, str] = {
    'access_token': os.environ['access_token']
}

likelihood: dict[str, int] = {
    'min_likelihood': 50,
    'max_likelihood': 50
}