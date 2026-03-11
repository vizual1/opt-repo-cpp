"""Runtime configuration management."""
from dataclasses import dataclass, field
from typing import Optional
from github import Auth, Github

from src.config.prompts import Prompts
from src.config.constants import *
from src.config.settings import LLMSettings, TestingSettings, GitHubSettings, ResourceSettings, ResourceSettingsCrawl
from src.utils.image_handling import dockerhub_containers, check_dockerhub

@dataclass
class Config:
    """
    GitHub Repository Collection, Structural, Build and Test Validation
    """
    # collect repositories from GitHub
    collect: bool = False
    # compiles and tests the most recent commit of the collected repositories
    test: bool = False 
    # indicates the number of repositories collected from GitHub before stopping
    repos: int = 0 
    # indicates the maximum number of stars of repositories collected from GitHub
    stars: int = 1000
    # path to file of already collected repositories that shouldn't be collected again
    blacklist: str = "" 
    # given a file of repositories, runs "--collect --test" without collecting repositories from GitHub 
    testcollect: bool = False 

    """
    GitHub Commit Collection, Structural, Build and Test Validation
    """
    # collect, filter, build and test commits from GitHub repositories
    commits: bool = False 
    # build and test commits from filtered commits (candidate), collected from "--commits" 
    testcommits: bool = False
    # filter type for collecting commits given repositories
    filter: str = ""
    # collect only up to limit amount of commits
    limit: int = -1

    """
    Docker Image Handling
    """
    # generates Docker image from "--commits" or "--testcommits" JSON results
    genimages: bool = False
    genforce: bool = False # overwrites Docker images already generated
    # tests the commits inside the Docker image and statistically evaluate the results
    testdocker: bool = False
    # saves the Docker container from running "--testdocker" as a .tar file
    tar: bool = False
    # does not save the Docker image from running "--testcommits"
    noimage: bool = False
    # Docker image name input
    docker: str = ""
    docker_image: str = field(init=False)

    """
    Dockerhub Handling
    """
    use_dockerhub: bool = True
    # environment variables
    dockerhub_user: str = field(init=False) # export DOCKERHUB_USER=...
    dockerhub_repo: str = field(init=False) # export DOCKERHUB_REPO=...
    # checks if the image is already uploaded to Dockerhub
    check_dockerhub: bool = False 
    # if check_dockerhub then all the Docker images on dockerhub_user/dockerhub_repo will be collected
    dockerhub_containers: list[str] = field(init=False)
    # pushes images to Dockerhub, requires DOCKER_HUB_USER and DOCKER_HUB_REPO environment variables 
    pushimages: bool = False
    # forces "docker push" to Dockerhub via "--pushimages"
    dockerhub_force: bool = False
    # pulls images from Dockerhub, requires DOCKER_HUB_USER and DOCKER_HUB_REPO environment variables 
    pullimages: bool = False

    """
    OpenHands Patch
    """
    # generates a patch
    patch: bool = False
    # prompt for generating a patch
    prompt: str = ""
    # test a patch
    testpatch: bool = False
    # path to diff file input for running "--testpatch"
    diff: str = ""
    
    input: str = ""
    output: str = ""
    repo: str = ""
    sha: str = ""
    
    # File paths
    repo_id: str = field(init=False)
    input_file: str = field(init=False)
    output_file: str = field(init=False)
    output_fail: str = "data/fail.txt"
    
    """
    Commit Analysis Settings
    """
    min_exec_time_improvement: float = 0.05
    min_p_value: float = 0.05
    overall_decline_limit: float = -0.01
    max_test_time: int = 1800 # in seconds
    min_stars: int = 20
    
    """
    Configurations Settings
    """
    llm: LLMSettings = field(default_factory=LLMSettings)
    testing: TestingSettings = field(default_factory=TestingSettings)
    github: GitHubSettings = field(default_factory=GitHubSettings)
    resources: ResourceSettings = field(default_factory=ResourceSettings)
    prompts: Prompts = field(default_factory=Prompts)

    """
    Constants
    """
    storage_paths: dict = field(default_factory=lambda: STORAGE_PATHS)
    valid_test_dirs: set = field(default_factory=lambda: VALID_TEST_DIRS)
    test_keywords: list = field(default_factory=lambda: TEST_KEYWORDS)
    docker_map: dict = field(default_factory=lambda: DOCKER_IMAGE_MAP)
    commits_time: dict = field(default_factory=lambda: COMMIT_TIME)
    valid_test_flags: dict = field(default_factory=lambda: VALID_TEST_FLAGS)
    
    """
    GitHub
    """
    _auth: Optional[Auth.Token] = field(init=False, default=None)
    _git: Optional[Github] = field(init=False, default=None)

    def __post_init__(self):
        self.repo_id = self.repo.removeprefix("https://github.com/").strip() if self.repo else self.repo
        self.input_file = self.input
        self.output_file = self.output
        self.docker_image = self.docker
        if self.testcollect:
            self.resources = ResourceSettingsCrawl()
        if self.use_dockerhub or self.check_dockerhub:
            self.dockerhub_user, self.dockerhub_repo = check_dockerhub()
        if self.check_dockerhub:
            self.dockerhub_containers = dockerhub_containers(self.dockerhub_user, self.dockerhub_repo)
        self._validate()
        self._setup_github()

    def _validate(self) -> None:
        """Validate configuration consistency."""
        if self.filter not in ("simple", "llm", "issue"):
            raise ValueError(f"Unknown filter type: {self.filter}")

        if self.stars < 0 or self.repos <= 0:
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