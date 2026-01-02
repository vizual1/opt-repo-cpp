import logging
from src.config.config import Config
from src.gh.collector import RepositoryCollector
from src.utils.writer import Writer
from github.Repository import Repository

class CollectionPipeline:
    """
    This class crawls popular GitHub repositories.
    """
    def __init__(self, config: Config):
        self.config = config

    def query_popular_repos(self) -> list[Repository]:
        collector = RepositoryCollector(config=self.config)
        repos = collector.query_popular_repos()
        logging.info(f"Found {len(repos)} repositories from collector.")
        for repo in repos:
            Writer(repo.full_name, self.config.output_file or self.config.storage_paths['popular']).write_repo()
        return repos