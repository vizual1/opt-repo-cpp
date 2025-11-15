import logging
from src.config.config import Config
from src.gh.crawler import RepositoryCrawler
from src.utils.writer import Writer

class CrawlerPipeline:
    """
    This class crawls popular GitHub repositories.
    """
    def __init__(self, config: Config):
        self.config = config

    def get_repos(self) -> list[str]:
        crawler = RepositoryCrawler(config=self.config)
        repo_ids = crawler.get_repos()
        logging.info(f"Found {len(repo_ids)} repositories from crawler.")
        for repo_id in repo_ids:
            Writer(repo_id, self.config.output_file or self.config.storage_paths['popular']).write_repo()
        return repo_ids