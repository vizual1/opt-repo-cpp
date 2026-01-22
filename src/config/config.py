"""Runtime configuration management."""
from dataclasses import dataclass, field
from typing import Optional
from github import Auth, Github

from src.config.constants import *
from src.config.settings import LLMSettings, TestingSettings, GitHubSettings, ResourceSettings, ResourceSettingsCrawl
from src.utils.image_handling import dockerhub_containers, check_dockerhub

@dataclass
class Config:
    # Core operation modes
    collect: bool = False
    testcollect: bool = False 
    commits: bool = False 
    testcommits: bool = False
    genimages: bool = False
    pushimages: bool = False
    testdocker: bool = False
    testdockerpatch: bool = False
    
    # Limits and filters
    limit: int = 10 # indicates the number of repositories collected from github before stopping
    stars: int = 1000 # indicates the maximum number of stars of repositories collected from github
    filter: str = "llm" # filter type for filtering commits
    filter_type: str = field(init=False)
    
    input: str = ""
    output: str = ""
    repo: str = ""
    genforce: bool = True # --genimages

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
    analyze: bool = False
    tar: bool = False

    # Dockerhub settings
    check_dockerhub: bool = True # checks if the image is already uploaded to dockerhub
    dockerhub_user: str = field(init=False) # export DOCKERHUB_USER=...
    dockerhub_repo: str = field(init=False) # export DOCKERHUB_REPO=...
    dockerhub_containers: list[str] = field(init=False)
    dockerhub_force: bool = True # forces docker push to dockerhub via --pushimages
    
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
    mannwhitney_improvement: float = 0.3
    max_test_time: int = 600 # in seconds
    min_stars: int = 20
    
    # Runtime objects
    _auth: Optional[Auth.Token] = field(init=False, default=None)
    _git: Optional[Github] = field(init=False, default=None)

    def __post_init__(self):
        self.filter_type = self.filter
        self.repo_id = self.repo.removeprefix("https://github.com/").strip() if self.repo else self.repo
        self.input_file = self.input
        self.output_file = self.output
        self.docker_image = self.docker
        if self.testcollect:
            self.resources = ResourceSettingsCrawl()
        self.dockerhub_user, self.dockerhub_repo = check_dockerhub()
        if self.check_dockerhub:
            self.dockerhub_containers = dockerhub_containers(self.dockerhub_user, self.dockerhub_repo)
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