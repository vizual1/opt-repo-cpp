import logging
from tqdm import tqdm
from src.config.config import Config
from src.utils.stats import RepoStats
from github.Repository import Repository
from src.gh.collector import RepositoryCollector
from src.core.filter.structure_filter import StructureFilter
from src.core.filter.process_filter import ProcessFilter
from src.utils.writer import Writer

class RepositoryPipeline:
    """
    This class takes a list of repositories, and tests and validates them.
    """
    def __init__(self, config: Config):
        self.config = config
        self.stats = RepoStats()
        self.valid_repos: list[Repository] = []

    def get_repos(self) -> list[str]:
        collector = RepositoryCollector(config=self.config)
        return collector.get_repos()

    def test_repos(self) -> None:
        collector = RepositoryCollector(self.config)
        repo_ids = collector.get_repos()
        if not repo_ids:
            logging.warning("No repositories found.")
            return

        logging.info(f"Found {len(repo_ids)} repositories.")
        for repo_id in tqdm(repo_ids, total=len(repo_ids), desc=f"Testing repositories...", mininterval=5):
            repo = self.config.git_client.get_repo(repo_id)
            structure = StructureFilter(repo, self.config)
            process = ProcessFilter(repo, self.config)

            try:
                if structure.is_valid() and process.valid_run("_".join(repo.full_name.split("/"))):
                    self.valid_repos.append(repo)
                    if self.config.popular or self.config.output_file:
                        Writer(repo_id, self.config.output_file or self.config.storage_paths['testcrawl']).write_repo()
            
                elif self.config.output_file:
                    Writer(repo_id, self.config.storage_paths['fail']).write_repo()

            except Exception as e:
                logging.exception(f"[{repo_id}] Error processing repository: {e}")
            
    def analyze_repos(self) -> None:
        collector = RepositoryCollector(config=self.config)
        repo_ids = collector.get_repos()
        if not repo_ids:
            logging.warning("No repositories found.")
            return
        
        logging.info(f"Found {len(repo_ids)} repositories.")
        for repo_id in tqdm(repo_ids, total=len(repo_ids), desc=f"Analyzing repositories...", mininterval=5):
            repo = self.config.git_client.get_repo(repo_id)
            structure = StructureFilter(repo, self.config)
            try:
                if structure.is_valid() and (self.config.popular or self.config.output_file):
                    Writer(repo_id, self.config.output_file).write_repo()
                self.stats += structure.stats

            except Exception as e:
                logging.exception(f"[{repo_id}] Error analyzing: {e}")

        self.stats.write_final_log()
