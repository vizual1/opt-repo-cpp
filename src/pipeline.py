import logging
from tqdm import tqdm
from github.Repository import Repository
from src.utils.crawler import RepositoryCrawler
from src.filter.structure_filter import StructureFilter
from src.filter.commit_filter import CommitFilter
from src.filter.flags_filter import FlagFilter
from src.filter.process_filter import ProcessFilter
from src.utils.stats import RepoStats, CommitStats
from src.utils.writer import Writer
from src.utils.tester import CommitTester
from github.Repository import Repository
from src.utils.dataclasses import Config 

class RepositoryPipeline:
    """
    This class crawls and filters GitHub repositories.
    """
    def __init__(self, url: str, config: Config):
        self.stats = RepoStats()
        self.url = url
        self.config = config
        self.valid_repos: list[Repository] = []

    def get_repos(self) -> None:
        crawl = RepositoryCrawler(url=self.url, config=self.config)
        repo_ids = crawl.get_repos()
        for repo_id in tqdm(repo_ids, total=len(repo_ids), desc=f"Testing repositories..."):
            structure = StructureFilter(repo_id, self.config.git)
            process = ProcessFilter(repo_id, self.config)
            if self.config.commits: 
                self.valid_repos.append(structure.repo)
                continue
            elif structure.is_valid() and process.valid_run():
                self.valid_repos.append(structure.repo)
                if self.config.popular or self.config.write:
                    Writer(structure.repo.full_name).write_repo(self.config.write)
            elif self.config.write:
                Writer(structure.repo.full_name).write_repo(self.config.write_fail)
           
    def analyze_repos(self) -> None:
        crawl = RepositoryCrawler(url=self.url, config=self.config)
        repo_ids = crawl.get_repos()
        for repo_id in tqdm(repo_ids, total=len(repo_ids), desc=f"Analyzing repositories..."):
            structure = StructureFilter(repo_id, self.config.git)
            if structure.is_valid() and (self.config.popular or self.config.write):
                Writer(structure.repo.full_name).write_repo(self.config.write)
            self.stats += structure.stats
        self.stats.write_final_log()


class CommitPipeline():
    """
    This class filters and saves the commit history of a repository.
    """
    def __init__(self, repo: Repository, sha: str, config: Config):
        self.stats = CommitStats()
        self.config = config
        self.repo = repo
        self.sha = sha
        if self.sha:
            self.commits = self.repo.get_commits(sha=sha) 
        else:
            self.commits = self.repo.get_commits() # TODO: set until to get commits > 2024?
        self.filtered_commits: list[str] = []

    def get_commits(self) -> None:
        for commit in tqdm(self.commits, total=self.commits.totalCount, desc=f"{self.repo.full_name} commits"):
            self.stats.num_commits += 1
            if not CommitFilter(commit, self.config.filter, self.repo.full_name).accept():
                continue
            writer = Writer(self.repo.full_name)
            self.filtered_commits.append(writer.file)
            self.stats.perf_commits += 1
            self.stats += writer.write_commit(commit, self.config.separate)
        self.stats.write_final_log()


class TesterPipeline:
    def __init__(self, config: Config, url: str = "", sha: str = ""):
        self.url = url
        self.sha = sha
        self.config = config     
        self.repo_ids = RepositoryCrawler(url=self.url, config=self.config).get_repos()  
    
    def test_commit(self):
        tester = CommitTester(sha=self.sha)
        for repo_id in tqdm(self.repo_ids, total=len(self.repo_ids), desc=f"Testing..."):
            commits, file = tester.get_commits(repo_id)
            for (new_sha, old_sha) in tqdm(commits, total=len(commits), desc=f"Testing filtered commits..."):
                new_path, old_path = tester.get_paths(file, new_sha)
                
                old_time = ProcessFilter(repo_id, self.config, old_path, old_sha).valid_commit_run("Old")
                new_time = ProcessFilter(repo_id, self.config, new_path, new_sha).valid_commit_run("New")
                
                logging.info(f"Old Final Time: {old_time}")
                logging.info(f"New Final Time: {new_time}")
