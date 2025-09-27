import logging
from dataclasses import dataclass, field
import src.config as conf
from github import Auth, Github

@dataclass
class Config:
    popular: bool = False
    stars: int = 1000
    limit: int = 10
    filter: str = "simple"
    separate: bool = False
    analyze: bool = False
    ignore_conflict: bool = False

    access_token: str = field(init=False)
    auth: Auth.Token = field(init=False)
    git: Github = field(init=False)

    def __post_init__(self):
        self.access_token = conf.github['access_token']
        self.auth = Auth.Token(self.access_token)
        self.git = Github(auth=self.auth)
        logging.info(f"GitHub rate limit: {self.git.get_rate_limit()}")
