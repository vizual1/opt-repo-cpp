"""Runtime configuration with environment variables and defaults."""
import os
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class LLMSettings:
    """LLM-related configuration."""
    api_key: str = field(default_factory=lambda: os.getenv('api_key', ''))
    base: bool = True
    base_url: str = "https://openrouter.ai/api/v1"
    model1: str = "openai/gpt-4.1-nano"
    model2: str = "openai/gpt-oss-20b:free"
    
    # Ollama settings
    ollama_enabled: bool = True
    ollama_url: str = "http://127.0.0.1:11434/api/generate"
    ollama_stage1_model: str = "qwen2.5:7b" #"llama3.1:8b"
    ollama_stage2_model: str = "qwen3:8b" #"deepseek-coder:6.7b"
    ollama_resolver_model: str = "qwen2.5:7b"
    
    # Behavior flags
    commit_message_only: bool = False
    issue_only: bool = False
    with_diff: bool = True
    
    cache_file: Path = field(default_factory=lambda: Path("cache/commit.json"))

@dataclass
class TestingSettings:
    """Testing-related configuration."""
    no_list_testing: bool = True
    warmup: int = 1
    commit_test_times: int = 30
    docker_test_dir: str = "/test_workspace"

@dataclass
class GitHubSettings:
    """GitHub API configuration."""
    access_token: str = field(default_factory=lambda: os.getenv('access_token', ''))
    
@dataclass
class ResourceSettings:
    """Docker resource limits."""
    cpuset_cpus: str = '4,5'
    mem_limit: str = '8g'
    memswap_limit: str = '8g'
    cpu_quota: int = 200000
    cpu_period: int = 100000
    jobs: int = 2