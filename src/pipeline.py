import logging
from tqdm import tqdm
from src.gh.crawler import RepositoryCrawler
from src.filter.structure_filter import StructureFilter
from src.filter.commit_filter import CommitFilter
from src.filter.process_filter import ProcessFilter
from src.utils.stats import RepoStats, CommitStats
from src.utils.writer import Writer
from src.utils.commit import Commit
from src.docker.tester import DockerTester
from src.utils.config import Config
from github.Repository import Repository

class BasePipeline:
    def __init__(self, config: Config):
        self.config = config

class CrawlerPipeline(BasePipeline):
    """
    This class crawls popular GitHub repositories.
    """
    def __init__(self, config: Config):
        super().__init__(config)

    def get_repos(self) -> list[str]:
        crawler = RepositoryCrawler(config=self.config)
        repos = crawler.get_repos()
        logging.info(f"Found {len(repos)} repositories from crawler.")
        for repo in repos:
            Writer(repo, self.config.output or self.config.storage['popular']).write_repo()
        return repos
    

class RepositoryPipeline(BasePipeline):
    """
    This class takes a list of repositories, and tests and validates them.
    """
    def __init__(self, config: Config):
        super().__init__(config)
        self.stats = RepoStats()
        self.valid_repos: list[Repository] = []

    def get_repos(self) -> list[str]:
        crawler = RepositoryCrawler(config=self.config)
        return crawler.get_repos()

    def test_repos(self) -> None:
        crawler = RepositoryCrawler(self.config)
        repos = crawler.get_repos()
        if not repos:
            logging.warning("No repositories found.")
            return

        logging.info(f"Found {len(repos)} repositories.")
        for repo in tqdm(repos, total=len(repos), desc=f"Testing repositories..."):
            try:
                structure = StructureFilter(repo, self.config)
                process = ProcessFilter(repo, self.config)

                if structure.is_valid() and process.valid_run("_".join(repo.split("/")), self.config.testing['docker_test_dir']):
                    self.valid_repos.append(structure.repo)
                    if self.config.popular or self.config.output:
                        Writer(structure.repo.full_name, self.config.output).write_repo()

                elif self.config.output:
                    Writer(structure.repo.full_name, self.config.output_fail).write_repo()

            except Exception as e:
                logging.exception(f"[{repo}] Error processing repository: {e}")

           
    def analyze_repos(self) -> None:
        crawler = RepositoryCrawler(config=self.config)
        repos = crawler.get_repos()
        if not repos:
            logging.warning("No repositories found.")
            return
        
        logging.info(f"Found {len(repos)} repositories.")
        for repo in tqdm(repos, total=len(repos), desc=f"Analyzing repositories..."):
            try:
                structure = StructureFilter(repo, self.config)
                if structure.is_valid() and (self.config.popular or self.config.output):
                    Writer(structure.repo.full_name, self.config.output).write_repo()
                self.stats += structure.stats

            except Exception as e:
                logging.exception(f"[{repo}] Error analyzing: {e}")

        self.stats.write_final_log()


class CommitPipeline(BasePipeline):
    """
    This class filters and saves the commit history of a repository.
    """
    def __init__(self, repo_id: str, config: Config):
        super().__init__(config)
        self.repo_id = repo_id
        self.repo = self.config.git.get_repo(self.repo_id)
        self.stats = CommitStats()
        self.filtered_commits: list[str] = []

        since = self.config.commits_dict['since']
        until = self.config.commits_dict['until']

        try:
            if self.config.sha:
                self.commits = self.repo.get_commits(sha=self.config.sha) 
            else:
                self.commits = self.repo.get_commits(sha=self.repo.default_branch, since=since, until=until)
        except Exception as e:
            logging.exception(f"[{self.repo.full_name}] Error fetching commits: {e}")
            self.commits = []
        

    def filter_commits(self) -> None:
        if not self.commits:
            logging.warning(f"[{self.repo.full_name}] No commits found")
            return
        
        for commit in tqdm(self.commits, desc=f"{self.repo.full_name} commits"):
            try:
                self.stats.num_commits += 1
                if not CommitFilter(commit, self.config, self.repo).accept():
                    continue
                
                writer = Writer(self.repo.full_name, self.config.output or self.config.storage['commits'])
                self.filtered_commits.append(writer.file or "")
                self.stats.perf_commits += 1
                self.stats += writer.write_commit(commit, self.config.separate)

            except Exception as e:
                logging.exception(f"[{self.repo.full_name}] Error processing commit: {e}")

        self.stats.write_final_log()


class CommitTesterPipeline(BasePipeline):
    """
    This class runs the commits and evaluates its performance.
    """
    def __init__(self, config: Config):
        super().__init__(config)
        self.commit = Commit(self.config.output or self.config.storage['commits'])   
        self.docker = DockerTester(self.config) 

    def test_commit(self) -> None:
        if self.config.input:
            self._input_tester()
        else:
            self._sha_tester()

    def _input_tester(self) -> None:
        crawler = RepositoryCrawler(self.config)
        repos = crawler.get_repos()  
        if not repos:
            logging.warning("No repositories found for commit testing.")
            return
        
        for repo in tqdm(repos, total=len(repos), desc=f"Testing..."):
            try: 
                commits, file = self.commit.get_commits(repo)
                for (new_sha, old_sha) in tqdm(commits, total=len(commits), desc=f"Testing filtered commits..."):
                    try:
                        new_path, old_path = self.commit.get_paths(file, new_sha)
                        self.docker.run_commit_pair(repo, new_sha, old_sha, new_path, old_path)

                    except Exception as e:
                        logging.exception(f"[{repo}] Error testing commits: {e}")

            except Exception as e:
                logging.exception(f"[{repo}] Error testing repository: {e}")

    def _sha_tester(self):
        if self.config.sha:
            commits = self.config.git.search_commits(f"hash:{self.config.sha}")
            for commit in commits:
                repo = commit.repository
                if not repo.fork:
                    file = "_".join(repo.full_name.split("/"))
                    commit = repo.get_commit(self.config.sha)
                    new_sha = self.config.sha
                    if not commit.parents:
                        logging.info(f"[{repo.full_name}] Commit {self.config.sha} has no parents (root commit).")
                        return
                    old_sha = commit.parents[0].sha
                    new_path, old_path = self.commit.get_paths(file, new_sha)
                    self.docker.run_commit_pair(repo.full_name, new_sha, old_sha, new_path, old_path)
                    break
            
        elif self.config.newsha and self.config.oldsha:
            commits = self.config.git.search_commits(f"hash:{self.config.newsha}")
            for commit in commits:
                repo = commit.repository
                if not repo.fork:
                    file = "_".join(repo.full_name.split("/"))
                    new_sha = self.config.newsha
                    old_sha = self.config.oldsha
                    new_path, old_path = self.commit.get_paths(file, new_sha)
                    self.docker.run_commit_pair(repo.full_name, new_sha, old_sha, new_path, old_path)
                    break
        else:
            logging.error("Wrong sha input")


class TesterPipeline(BasePipeline):
    """
    This class runs the Docker image, evaluates its performance or compares its performance to the mounted project.
    """
    def __init__(self, config: Config):
        super().__init__(config)
        self.docker = DockerTester(self.config)

    def test(self):
        if self.config.input:
            self.docker.test_input_folder()
        
        if self.config.docker and self.config.mount:
            self.docker.test_mounted_against_docker(self.config.docker, self.config.mount)
        
        if self.config.newsha:
            raise NotImplementedError("not implemented")
        
        if self.config.oldsha:
            raise NotImplementedError("not implemented")
        
    
