
import logging
from src.pipeline import CrawlerPipeline, RepositoryPipeline, CommitPipeline, CommitTesterPipeline
from src.utils.dataclasses import Config

class Controller:
    """
    The Controller class initiates the main operations of the system based on the configurations.
    It is the central manager for pipelines that handle various stages of GitHub repository analysis.
    
    This class supports the following operations:
    - **Crawl popular repositories** from GitHub to build a dataset.
    - **Filter, test and validate repositories** for structure, build and test success.
    - **Gather and filter commits** from repositories.
    - **Build and test commits and their parents** to evaluate performance.
    """
    def __init__(self, config: Config):
        self.config = config

    def run(self) -> None:
        logging.info("Starting controller...")

        try:
            if self.config.popular:
                self._popular()
            
            if self.config.testcrawl:
                self._testcrawl()

            if self.config.commits:
                self._commits()

            if self.config.testcommits:
                self._testcommits()

            if not any([self.config.popular, self.config.testcrawl, self.config.commits, self.config.testcommits]):
                logging.warning("No operation selected. Use --popular, --testcrawl, --commits, or --testcommits.")

        except Exception as e:
            logging.error(f"Controller encountered an error: {e}", exc_info=True)

        finally:
            logging.info("Controller execution completed.")

    def _popular(self) -> None:
        logging.info("Crawling popular GitHub repositories...")
        CrawlerPipeline(self.config).get_repos()
        
    def _testcrawl(self) -> None:
        logging.info("Testing and validating GitHub repositories...")

        repo_pipeline = RepositoryPipeline(self.config)

        if self.config.analyze:
            repo_pipeline.analyze_repos()
            logging.info("Repository analysis completed.")
            return

        repo_pipeline.test_repos()
        logging.info(f"Found {len(repo_pipeline.valid_repos)} valid repositories.")

    def _commits(self) -> None:
        logging.info("Gathering and filtering commits...")
        repos = RepositoryPipeline(self.config).get_repos()
        logging.info(f"Found {len(repos)} repositories.")
        for repo in repos:
            CommitPipeline(repo, self.config).get_commits()

    def _testcommits(self) -> None:
        logging.info("Testing commits...")
        tester_pipeline = CommitTesterPipeline(self.config)
        tester_pipeline.test_commit()
