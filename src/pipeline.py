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
            if self.config.commits or structure.is_valid():
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
            if structure.analyze() and (self.config.popular or self.config.write):
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
            self.commits = self.repo.get_commits()
        self.filtered_commits: list[str] = []

    def get_commits(self) -> None:
        for commit in tqdm(self.commits, total=self.commits.totalCount, desc=f"{self.repo.full_name} commits"):
            self.stats.num_commits += 1
            if CommitFilter(commit, self.config.filter, self.repo.full_name).accept():
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
        for repo_id in tqdm(self.repo_ids, total=len(self.repo_ids), desc=f"Testing filtered commits..."):
            commits, file = tester.get_commits(repo_id)
            #repo = self.config.git.get_repo(repo_id)
            for (current_sha, parent_sha) in commits:
                current_path, parent_path = tester.get_paths(file, current_sha)
                current_filter = StructureFilter(repo_id, self.config.git, current_path, current_sha)
                parent_filter = StructureFilter(repo_id, self.config.git, parent_path, parent_sha)
                logging.info(f"Testing {repo_id} ({current_sha} and {parent_sha})...")
                if current_filter.is_valid():
                    logging.info(f"commit cmake and ctest successful ({repo_id}/{current_sha})")
                    if parent_filter.is_valid():
                        logging.info(f"parent cmake and ctest successful ({repo_id}/{parent_sha})")
                        current_test_time = current_filter.process.test_time if current_filter.process else 0.0
                        parent_test_time = parent_filter.process.test_time if parent_filter.process else 0.0
                        logging.info(f"Commit Test Time {current_test_time}")
                        logging.info(f"Parent Test Time {parent_test_time}")
                    else:
                        logging.error(f"parent cmake and ctest failed ({repo_id}/{parent_sha})")
                else:
                    logging.error(f"commit cmake and ctest failed ({repo_id}/{parent_sha})")


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
