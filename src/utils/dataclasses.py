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

    storage: dict[str, str] = field(init=False)
    llm: dict[str, Any] = field(init=False)
    likelihood: dict[str, int] = field(init=False)
    testing: dict[str, Any] = field(init=False)
    valid_test_dir: set[str] = field(init=False)
    commits_since: datetime = field(init=False)

    access_token: str = field(init=False)
    auth: Auth.Token = field(init=False)
    git: Github = field(init=False)

    def __post_init__(self):
        self.storage = conf.storage
        self.llm = conf.llm
        self.likelihood = conf.likelihood
        self.testing = conf.testing
        self.valid_test_dir = conf.valid_test_dir
        self.commits_since = conf.commits_since
        
        self.access_token = conf.github['access_token']
        self.auth = Auth.Token(self.access_token)
        self.git = Github(auth=self.auth)
        

@dataclass
class CommitAnalysisResult:
    repo_name: str
    commit_sha: str
    parent_sha: str
    commit_test_time: Optional[float] = None
    parent_test_time: Optional[float] = None
    improvement_percent: Optional[float] = None
    is_significant: bool = False
    docker_image_tag: Optional[str] = None
    analyzed_at: datetime = field(default_factory=datetime.now)
    