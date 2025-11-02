import logging
from dataclasses import dataclass, field
import src.config as conf
from github import Auth, Github
from typing import Any

@dataclass
class Config:
    popular: bool = False
    testcrawl: bool = False 
    commits: bool = False 
    testcommits: bool = False
    test: bool = False
    
    limit: int = 10
    stars: int = 1000

    repo_url: str = ""
    input: str = ""
    output: str = ""
    output_fail: str = "data/fail.txt"

    sha: str = ""
    newsha: str = ""
    oldsha: str = ""

    filter: str = "simple"
    docker: str = ""
    mount: str = ""
    separate: bool = False
    analyze: bool = False

    storage: dict[str, str] = field(default_factory=lambda: conf.storage)
    llm: dict[str, Any] = field(default_factory=lambda: conf.llm)
    likelihood: dict[str, int] = field(default_factory=lambda: conf.likelihood)
    testing: dict[str, Any] = field(default_factory=lambda: conf.testing)
    valid_test_dir: set[str] = field(default_factory=lambda: conf.valid_test_dir)
    commits_dict: dict[str, Any] = field(default_factory=lambda: conf.commits)
    docker_map: dict[str, str] = field(default_factory=lambda: conf.docker_map)
    test_keywords: list[str] = field(default_factory=lambda: conf.test_keywords)

    access_token: str = field(default_factory=lambda: conf.github.get("access_token", ""))
    auth: Auth.Token = field(init=False)
    git: Github = field(init=False)

    def __post_init__(self):
        self.storage = conf.storage
        self.llm = conf.llm
        self.likelihood = conf.likelihood
        self.testing = conf.testing
        self.valid_test_dir = conf.valid_test_dir

        if not self.access_token:
            raise ValueError("Missing GitHub access token (set via environment variable or config).")
        
        self.auth = Auth.Token(self.access_token)
        self.git = Github(auth=self.auth)
    
        self._validate()

    def _validate(self) -> None:
        """Perform basic consistency checks."""
        if self.filter not in ("simple", "llm", "custom"):
            raise ValueError(f"Unknown filter type: {self.filter}")

        if self.stars < 0 or self.limit <= 0:
            raise ValueError("Stars and limit must be positive.")

        if self.testing['docker_test_dir'] == "/workspace":
            raise ValueError("Docker will mount on '/workspace' making the resulting Docker image " \
                "non-persistent. Please change 'docker_test_dir' in src/config.py")
        
        if self.limit > 1000:
            logging.warning("High limit value may result in rate limiting or timeouts")
        
        
        

