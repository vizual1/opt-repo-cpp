"""Runtime configuration management."""
import logging
from dataclasses import dataclass, field
from typing import Optional
from github import Auth, Github

from src.config.constants import *
from src.config.settings import LLMSettings, TestingSettings, GitHubSettings, ResourceSettings, ResourceSettingsCrawl
from src.config.prompts import STAGE1_PROMPT, DIFF_PROMPT, STAGE2_PROMPT, RESOLVER_PROMPT

@dataclass
class Config:
    # Core operation modes
    collect: bool = False
    testcollect: bool = False 
    commits: bool = False 
    testcommits: bool = False
    dockerimages: bool = False
    testdocker: bool = False
    testdockerpatch: bool = False
    
    # Limits and filters
    limit: int = 10
    stars: int = 1000
    filter: str = "llm"
    filter_type: str = field(init=False)
    
    input: str = ""
    output: str = ""
    repo: str = ""

    # File paths
    repo_id: str = field(init=False)
    input_file: str = field(init=False)
    output_file: str = field(init=False)
    output_fail: str = "data/fail.txt"
    
    # Commit SHAs
    sha: str = ""
    
    # Docker settings
    docker: str = ""
    docker_image: str = field(init=False)
    mount: str = ""
    mount_path: str = field(init=False)
    analyze: bool = False
    
    # Configuration sections
    llm: LLMSettings = field(default_factory=LLMSettings)
    testing: TestingSettings = field(default_factory=TestingSettings)
    github: GitHubSettings = field(default_factory=GitHubSettings)
    resources: ResourceSettings = field(default_factory=ResourceSettings)
    
    # Constants (read-only)
    storage_paths: dict = field(default_factory=lambda: STORAGE_PATHS)
    valid_test_dirs: set = field(default_factory=lambda: VALID_TEST_DIRS)
    test_keywords: list = field(default_factory=lambda: TEST_KEYWORDS)
    docker_map: dict = field(default_factory=lambda: DOCKER_IMAGE_MAP)
    commits_time: dict = field(default_factory=lambda: COMMIT_TIME)
    valid_test_flags: dict = field(default_factory=lambda: VALID_TEST_FLAGS)
    
    # Commit analysis settings
    min_exec_time_improvement: float = 0.05
    min_p_value: float = 0.05
    overall_decline_limit: float = -0.01
    min_likelihood: int = 50
    max_likelihood: int = 90
    
    # Prompts
    stage1_prompt: str = STAGE1_PROMPT
    diff_prompt: str = DIFF_PROMPT
    stage2_prompt: str = STAGE2_PROMPT
    resolver_prompt: str = RESOLVER_PROMPT
    
    # Runtime objects
    _auth: Optional[Auth.Token] = field(init=False, default=None)
    _git: Optional[Github] = field(init=False, default=None)

    def __post_init__(self):
        self.filter_type = self.filter
        self.repo_id = self.repo.removeprefix("https://github.com/").strip() if self.repo else self.repo
        self.input_file = self.input
        self.output_file = self.output
        self.docker_image = self.docker
        self.mount_path = self.mount
        if self.testcollect:
            self.resources = ResourceSettingsCrawl()
        self._validate()
        self._setup_github()

    def _validate(self) -> None:
        """Validate configuration consistency."""
        if self.filter_type not in ("simple", "llm", "issue"):
            raise ValueError(f"Unknown filter type: {self.filter_type}")

        if self.stars < 0 or self.limit <= 0:
            raise ValueError("Stars and limit must be positive.")

        if str(self.testing.docker_test_dir) == "/workspace":
            raise ValueError("Docker test directory cannot be '/workspace'")
            
        if not self.github.access_token:
            raise ValueError("GitHub access token is required")
        
        if self.sha and not self.repo:
            raise ValueError("SHA value needs an accompanying repository owner/name")

    def _setup_github(self):
        """Initialize GitHub client."""
        self._auth = Auth.Token(self.github.access_token)
        self._git = Github(auth=self._auth)

    @property
    def git_client(self) -> Github:
        """Get the GitHub client (read-only)."""
        if self._git is None:
            raise RuntimeError("GitHub client not initialized")
        return self._git