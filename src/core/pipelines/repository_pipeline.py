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

    def test_repos(self, repos: list[Repository] = []) -> None:
        if repos:
            repo_ids = [repo.full_name for repo in repos]
        else:
            collector = RepositoryCollector(self.config)
            repo_ids = collector.get_repos()

        if not repo_ids:
            logging.warning("No repositories found.")
            return

        logging.info(f"Found {len(repo_ids)} repositories.")
        structure = StructureFilter(self.config)
        process = ProcessFilter(self.config)
        for repo_id in tqdm(repo_ids, total=len(repo_ids), desc=f"Testing repositories...", mininterval=5):
            repo = self.config.git_client.get_repo(repo_id)
            
            try:
                if structure.is_valid(repo) and process.valid_run("_".join(repo.full_name.split("/")), repo):
                    self.valid_repos.append(repo)
                    if self.config.collect or self.config.output_file:
                        Writer(repo_id, self.config.output_file or self.config.storage_paths['testcollect']).write_repo()
            
                elif self.config.output_file:
                    Writer(repo_id, self.config.storage_paths['fail']).write_repo()

            except Exception as e:
                logging.exception(f"[{repo_id}] Error processing repository: {e}")
