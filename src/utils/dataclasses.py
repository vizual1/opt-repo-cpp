from datetime import datetime 
from dataclasses import dataclass, field
import src.config as conf
from github import Auth, Github
from typing import Optional, Any

@dataclass
class Config:
    crawl: bool = False 
    commits: bool = False 
    docker: bool = False
    test: bool = False
    popular: bool = False
    stars: int = 1000
    limit: int = 10
    read: str = ""
    write: str = ""
    write_fail: str = "data/fail.txt"
    filter: str = "simple"
    separate: bool = False
    analyze: bool = False

    storage: dict[str, str] = field(default_factory=lambda: conf.storage)
    llm: dict[str, Any] = field(default_factory=lambda: conf.llm)
    likelihood: dict[str, int] = field(default_factory=lambda: conf.likelihood)
    testing: dict[str, Any] = field(default_factory=lambda: conf.testing)
    improvement_threshold: float = field(init=False)
    valid_test_dir: set[str] = field(default_factory=lambda: conf.valid_test_dir)
    commits_since: datetime = field(default_factory=lambda: conf.commits_since)
    docker_map: dict[str, str] = field(default_factory=lambda: conf.docker_map)

    access_token: str = field(default_factory=lambda: conf.github.get("access_token", ""))
    auth: Auth.Token = field(init=False)
    git: Github = field(init=False)


    def __post_init__(self):
        self.storage = conf.storage
        self.llm = conf.llm
        self.likelihood = conf.likelihood
        self.testing = conf.testing
        self.improvement_threshold = self.testing['improvement_threshold']
        self.valid_test_dir = conf.valid_test_dir

        if not self.access_token:
            raise ValueError("Missing GitHub access token (set via environment variable or config).")
        
        self.auth = Auth.Token(self.access_token)
        self.git = Github(auth=self.auth)
    
        self._validate()


    def _validate(self):
        """Perform basic consistency checks."""
        if self.filter not in ("simple", "llm", "custom"):
            raise ValueError(f"Unknown filter type: {self.filter}")

        if self.stars < 0 or self.limit <= 0:
            raise ValueError("Stars and limit must be positive.")