import logging
from src.config.config import Config
from src.gh.crawler import RepositoryCrawler
from src.utils.writer import Writer
from github.Repository import Repository

class CrawlerPipeline:
    """
    This class crawls popular GitHub repositories.
    """
    def __init__(self, config: Config):
        self.config = config

    def get_repos(self) -> list[Repository]:
        crawler = RepositoryCrawler(config=self.config)
        repos = crawler.get_repos()
        logging.info(f"Found {len(repos)} repositories from crawler.")
        for repo in repos:
            Writer(repo.full_name, self.config.output_file or self.config.storage_paths['popular']).write_repo()
        return repos