import logging
from tqdm import tqdm
from datetime import datetime, timezone
from src.utils.crawler import RepositoryCrawler
from src.filter.structure_filter import StructureFilter
from src.filter.commit_filter import CommitFilter
from src.filter.process_filter import ProcessFilter
from src.utils.stats import RepoStats, CommitStats
from src.utils.writer import Writer
from src.utils.tester import CommitTester
from src.utils.dataclasses import Config 
from github.Repository import Repository

class RepositoryPipeline:
    """
    This class crawls and filters GitHub repositories.
    """

    def __init__(self, url: str, config: Config):
        self.url = url
        self.config = config
        self.stats = RepoStats()
        self.valid_repos: list[Repository] = []


    def get_repos(self) -> None:
        crawl = RepositoryCrawler(url=self.url, config=self.config)
        repos = crawl.get_repos()

        if not repos:
            logging.warning("No repositories found from crawler.")
            return

        for repo in tqdm(repos, total=len(repos), desc=f"Testing repositories..."):
            try:
                structure = StructureFilter(repo, self.config.git)
                process = ProcessFilter(repo, self.config)
                
                if self.config.commits: 
                    self.valid_repos.append(structure.repo)
                    continue

                elif structure.is_valid() and process.valid_run():
                    self.valid_repos.append(structure.repo)
                    if self.config.popular or self.config.write:
                        Writer(structure.repo.full_name).write_repo(self.config.write)

                elif self.config.write:
                    Writer(structure.repo.full_name).write_repo(self.config.write_fail)

            except Exception as e:
                logging.exception(f"[{repo}] Error processing repository: {e}")

           
    def analyze_repos(self) -> None:
        crawl = RepositoryCrawler(url=self.url, config=self.config)
        repos = crawl.get_repos()

        for repo in tqdm(repos, total=len(repos), desc=f"Analyzing repositories..."):
            try:
                structure = StructureFilter(repo, self.config.git)
                if structure.is_valid() and (self.config.popular or self.config.write):
                    Writer(structure.repo.full_name).write_repo(self.config.write)
                self.stats += structure.stats

            except Exception as e:
                logging.exception(f"[{repo}] Error analyzing: {e}")

        self.stats.write_final_log()


class CommitPipeline():
    """
    This class filters and saves the commit history of a repository.
    """
    def __init__(self, repo: Repository, sha: str, config: Config):
        self.repo = repo
        self.sha = sha
        self.config = config
        self.stats = CommitStats()
        self.filtered_commits: list[str] = []

        since = self.config.commits_since
        until = datetime.now(timezone.utc)

        try:
            if self.sha:
                self.commits = self.repo.get_commits(sha=sha) 
            else:
                self.commits = self.repo.get_commits(since=since, until=until)
        except Exception as e:
            logging.exception(f"[{self.repo.full_name}] Error fetching commits: {e}")
            self.commits = []
        

    def get_commits(self) -> None:
        if not self.commits:
            logging.warning(f"[{self.repo.full_name}] No commits found")
            return
        
        for commit in tqdm(self.commits, desc=f"{self.repo.full_name} commits"):
            try:
                self.stats.num_commits += 1
                if not CommitFilter(commit, self.config.filter, self.repo.full_name).accept():
                    continue

                writer = Writer(self.repo.full_name)
                self.filtered_commits.append(writer.file or "")
                self.stats.perf_commits += 1
                self.stats += writer.write_commit(commit, self.config.separate)

            except Exception as e:
                logging.exception(f"[{self.repo.full_name}] Error processing commit: {e}")

        self.stats.write_final_log()


class TesterPipeline:
    def __init__(self, config: Config, url: str = "", sha: str = ""):
        self.url = url
        self.sha = sha
        self.config = config     
        self.repos = RepositoryCrawler(url=self.url, config=self.config).get_repos()  

    
    def test_commit(self):
        if not self.repos:
            logging.warning("No repositories found for testing.")
            return

        tester = CommitTester(sha=self.sha)
        for repo in tqdm(self.repos, total=len(self.repos), desc=f"Testing..."):
            try:
                commits, file = tester.get_commits(repo)
                for (new_sha, old_sha) in tqdm(commits, total=len(commits), desc=f"Testing filtered commits..."):
                    try:
                        new_path, old_path = tester.get_paths(file, new_sha)
                        
                        old_time = ProcessFilter(repo, self.config, old_path, old_sha).valid_commit_run("Old")
                        new_time = ProcessFilter(repo, self.config, new_path, new_sha).valid_commit_run("New")
                        
                        logging.info(f"{repo}: Old={old_time:.2f}s, New={new_time:.2f}s")

                        if new_time <= self.config.improvement_threshold*old_time:
                            Writer(repo).write_improve(new_sha, old_sha)

                    except Exception as e:
                        logging.exception(f"[{repo}] Error testing commits: {e}")

            except Exception as e:
                logging.exception(f"[{repo}] Error testing repository: {e}")