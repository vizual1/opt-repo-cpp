import logging
from tqdm import tqdm
from src.utils.crawler import RepositoryCrawler
from src.utils.filter import StructureFilter, CommitFilter
from src.utils.statistics import RepoStats, CommitStats
from src.utils.writer import Writer
from github.Repository import Repository
from src.docker.generator import DockerBuilder

class Pipeline:
    """"""
    def __init__(self, crawl: bool = False, docker: bool = False, test: bool = False,
                 # crawling arguments
                 url: str = "", popular: bool = False, stars: int = 1000, limit: int = 10,
                 sha: str = "", filter: str = "simple", separate: bool = False, analyze: bool = False,
                 # docker building arguments
                 ignore_conflict: bool = False):
        
        self.crawl, self.docker, self.test = crawl, docker, test

        self.url, self.popular, self.stars, self.limit = url, popular, stars, limit
        self.sha, self.filter, self.separate, self.analyze = sha, filter, separate, analyze

        self.ignore_conflict = ignore_conflict

    def run(self):
        if self.crawl:
            logging.info("Crawling GitHub repositories...")
            self._crawl()
        if self.docker:
            logging.info("Building Dockerfile...")
            self._docker()
        if self.test:
            logging.info("Testing commits...")
        
    def _crawl(self):
        repo_pipeline = RepositoryPipeline(url=self.url, popular=self.popular, stars=self.stars, limit=self.limit)
        if self.analyze:
            repo_pipeline.analyze_repos()
        else:
            repo_pipeline.get_repos()
            valid_repos = repo_pipeline.valid_repos
            for repo in valid_repos:
                commit_pipeline = CommitPipeline(repo=repo, sha=self.sha, filter=self.filter, separate=self.separate)
                commit_pipeline.get_commits()
    
    def _docker(self):
        docker = DockerBuilder(url=self.url, sha=self.sha, ignore_conflict=self.ignore_conflict)
        docker.create()


class RepositoryPipeline:
    """"""
    def __init__(self, url: str = "", popular: bool = False, stars: int = 1000, limit: int = 10):
        super().__init__()
        self.stats = RepoStats()
        self.url = url
        self.popular = popular
        self.stars = stars
        self.limit = limit

        self.valid_repos: list[Repository] = []

    def get_repos(self) -> None:
        crawl = RepositoryCrawler(url=self.url, popular=self.popular, stars=self.stars, limit=self.limit)
        repo_ids = crawl.get_repos()
        for repo_id in tqdm(repo_ids, total=len(repo_ids), desc=f"Fetching commit history..."):
            structure = StructureFilter(repo_id, crawl.git)
            if structure.is_valid():
                Writer(structure.repo.full_name).write_repo()
                self.valid_repos.append(structure.repo)
                
    def analyze_repos(self) -> None:
        crawl = RepositoryCrawler(url=self.url, popular=self.popular, stars=self.stars, limit=self.limit)
        repo_ids = crawl.get_repos()
        for repo_id in tqdm(repo_ids, total=len(repo_ids), desc=f"Fetching commit history..."):
            structure = StructureFilter(repo_id, crawl.git)
            structure.analyze()
            Writer(structure.repo.full_name).write_repo()
            self.stats.test_dirs += structure.test_dirs
        self.stats.write_final_log()


class CommitPipeline:
    """"""
    def __init__(self, repo: Repository, sha: str = "", filter: str = "simple", separate: bool = False):
        self.stats = CommitStats()
        self.repo = repo
        self.sha = sha
        if self.sha:
            self.commits = self.repo.get_commits(sha=sha)
        else:
            self.commits = self.repo.get_commits()
        self.filter = filter
        self.separate = separate

    def get_commits(self) -> None:
        for commit in tqdm(self.commits, total=self.commits.totalCount, desc=f"{self.repo.full_name} commits"):
            if CommitFilter(commit, self.filter, self.repo.full_name).accept():
                Writer(self.repo.full_name).write_commit(self.stats, commit, self.separate)
            self.stats.num_commits += 1
        self.stats.write_final_log()