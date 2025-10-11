import logging
from tqdm import tqdm
from github.Repository import Repository
from src.utils.crawler import RepositoryCrawler
from src.filter.structure_filter import StructureFilter
from src.filter.commit_filter import CommitFilter
from src.utils.stats import RepoStats, CommitStats
from src.utils.writer import Writer
from src.utils.tester import CommitTester
from github.Repository import Repository
from src.utils.dataclasses import Config 

class RepositoryPipeline:
    """
    This class crawls and filters GitHub repositories.
    """
    def __init__(self, url: str, config: Config = Config()):
        self.stats = RepoStats()
        self.url = url
        self.config = config
        self.valid_repos: list[Repository] = []

    def get_repos(self) -> None:
        crawl = RepositoryCrawler(self.url, config=self.config)
        repo_ids = crawl.get_repos()
        for repo_id in tqdm(repo_ids, total=len(repo_ids), desc=f"Fetching commit history..."):
            try:
                structure = StructureFilter(repo_id, self.config.git)
                if structure.is_valid():
                    self.valid_repos.append(structure.repo)
                    if self.config.popular or self.config.write:
                        Writer(structure.repo.full_name).write_repo(self.config.write)
                elif self.config.write:
                    Writer(structure.repo.full_name).write_repo(self.config.write_fail)
            except Exception as e:
                logging.warning(f"Exception: {e}")
                continue
           
    def analyze_repos(self) -> None:
        crawl = RepositoryCrawler(self.url, config=self.config)
        repo_ids = crawl.get_repos()
        for repo_id in tqdm(repo_ids, total=len(repo_ids), desc=f"Fetching commit history..."):
            try:
                structure = StructureFilter(repo_id, self.config.git)
                if structure.analyze() and (self.config.popular or self.config.write):
                    Writer(structure.repo.full_name).write_repo(self.config.write)
                self.stats += structure.stats
            except Exception as e:
                logging.warning(f"Exception: {e}")
                continue
        self.stats.write_final_log()


class CommitPipeline():
    """
    This class filters and saves the commit history of a repository.
    """
    def __init__(self, repo: Repository, sha: str, config: Config = Config()):
        self.stats = CommitStats()
        self.config = config
        self.repo = repo
        self.sha = sha
        if self.sha:
            self.commits = self.repo.get_commits(sha=sha)
        else:
            self.commits = self.repo.get_commits()

    def get_commits(self) -> None:
        for commit in tqdm(self.commits, total=self.commits.totalCount, desc=f"{self.repo.full_name} commits"):
            if CommitFilter(commit, self.config.filter, self.repo.full_name).accept():
                self.stats += Writer(self.repo.full_name).write_commit(commit, self.config.separate)
        self.stats.write_final_log()


class TesterPipeline:
    def __init__(self, url: str = "", sha: str = "", config: Config = Config()):
        self.url = url
        self.sha = sha
        self.config = config     
        self.repo_ids = RepositoryCrawler(url=self.url).get_repos()  
    
    def test_commit(self):
        tester = CommitTester(sha=self.sha, ignore_conflict=self.config.ignore_conflict)
        for repo_id in tqdm(self.repo_ids, total=len(self.repo_ids), desc=f"Testing filtered commits..."):
            commits, file = tester.get_commits(repo_id)
            repo = self.config.git.get_repo(repo_id)
            for (current_sha, parent_sha) in commits:
                current_path, parent_path = tester.get_paths(file, current_sha)
                # TODO: need test, maybe use CMakeProcess
                current_filter = StructureFilter(repo_id, self.config.git, current_path, current_sha)
                parent_filter = StructureFilter(repo_id, self.config.git, parent_path, parent_sha)
                current_process = tester.create_process(current_filter.analyzer, current_path)
                parent_process = tester.create_process(parent_filter.analyzer, parent_path)
                if (current_process.clone_repo(repo_id, current_path, branch=current_sha) and 
                    parent_process.clone_repo(repo_id, parent_path, branch=parent_sha)):
                    if current_filter.is_valid() and parent_filter.is_valid():
                        if current_process.build() and parent_process.build():
                            current_test_exec = current_filter.analyzer.parser.find_ctest_exec()
                            current_process.test(current_test_exec)
                            parent_test_exec = parent_filter.analyzer.parser.find_ctest_exec()
                            parent_process.test(parent_test_exec)

    def test_configure(self):
        for repo_id in tqdm(self.repo_ids, total=len(self.repo_ids), desc=f"Configuring Repositories..."):
            return

    def test_build(self):
        self.test_configure()
        for repo_id in tqdm(self.repo_ids, total=len(self.repo_ids), desc=f"Building Repositories..."):
            return
    
    def test_ctest(self):
        self.test_build()
        for repo_id in tqdm(self.repo_ids, total=len(self.repo_ids), desc=f"Testing Repositories..."):
            return 
