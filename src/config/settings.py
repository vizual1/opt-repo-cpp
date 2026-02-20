"""Runtime configuration with environment variables and defaults."""
import os
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class LLMSettings:
    """LLM-related configuration."""
    api_key: str = field(default_factory=lambda: os.getenv('LLM_API_KEY', ''))
    base: bool = True
    base_url: str = "https://openrouter.ai/api/v1"
    model1: str = "openai/gpt-5-mini"
    model2: str = "openai/gpt-5-mini"
    
    # Ollama settings
    ollama_enabled: bool = False
    ollama_url: str = "http://127.0.0.1:11434/api/generate"
    ollama_stage1_model: str = "qwen2.5:7b"
    ollama_diff_model: str = "qwen2.5-coder:7b"
    ollama_stage2_model: str = "qwen3:8b"
    ollama_resolver_model: str = "qwen3:8b"
    
    # Behavior flags
    commit_message_only: bool = False
    issue_only: bool = False
    with_diff: bool = True

    # OpenHands settings
    sandbox_base_container_image: str = "ghcr.io/openhands/runtime:oh_v1.3.0_odjrubqcfxjb4y1s_kxyxnblfp0d1rp6p"
    openhands_model: str = "docker.openhands.dev/openhands/openhands:1.3" 
    docker_socket: str = "/var/run/docker.sock"
    
    cache_file: Path = field(default_factory=lambda: Path("cache/commit.json"))

@dataclass
class TestingSettings:
    """Testing-related configuration."""
    no_list_testing: bool = True
    warmup: int = 0
    commit_test_times: int = 1
    docker_test_dir: str = "/test_workspace"

@dataclass
class GitHubSettings:
    """GitHub API configuration."""
    access_token: str = field(default_factory=lambda: os.getenv('GITHUB_ACCESS_TOKEN', ''))
    
@dataclass
class ResourceSettings:
    """Docker resource limits for --testcommits, --testdocker, --testpatch"""
    cpuset_cpus: str = ''
    mem_limit: str = '8g'
    memswap_limit: str = '8g'
    cpu_quota: int = 200000
    cpu_period: int = 100000
    jobs: int = 1 # running cmake build with -j = jobs
    max_parallel_jobs: int = 8 # tests multiple test commits at the same time
    
@dataclass
class ResourceSettingsCrawl(ResourceSettings):
    """Docker resource limits for --testcollect"""
    cpuset_cpus: str = '1-4'
    mem_limit: str = '32g'
    memswap_limit: str = '32g'
    cpu_quota: int = 400000
    cpu_period: int = 100000
    jobs: int = 4