
import logging
from src.core.pipelines.pipeline import (
    CrawlerPipeline, 
    RepositoryPipeline, 
    CommitPipeline, 
    CommitTesterPipeline, 
    TesterPipeline
)
from src.config.config import Config

class Controller:
    """
    The Controller class initiates the main operations of the system based on the configurations.
    It is the central manager for pipelines that handle various stages of GitHub repository analysis.
    
    This class supports the following operations:
    - **Crawl popular repositories** from GitHub to build a dataset.
    - **Filter, test and validate repositories** for structure, build and test success.
    - **Gather and filter commits** from repositories.
    - **Build and test new commits and old commits** to compare performance.
    - **Run docker images to build and test new commits and old commits** to compare performance.
    - **Run docker images to build and test old commits and the mounted modified commit** to compare performance.
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

            if self.config.test:
                self._test()

            if not any([self.config.popular, self.config.testcrawl, self.config.commits, self.config.testcommits, self.config.test]):
                logging.warning("No operation selected. Use --popular, --testcrawl, --commits, --testcommits, or --test")

        except Exception as e:
            logging.error(f"Controller encountered an error: {e}", exc_info=True)

        finally:
            logging.info("Controller execution completed.")

    def _popular(self) -> None:
        logging.info("Crawling popular GitHub repositories...")
        pipeline = CrawlerPipeline(self.config)
        pipeline.get_repos()
        logging.info("Popular repository crawling completed.")
        
    def _testcrawl(self) -> None:
        logging.info("Testing and validating GitHub repositories...")
        repo_pipeline = RepositoryPipeline(self.config)

        if self.config.analyze:
            logging.info("Starting repository analysis...")
            repo_pipeline.analyze_repos()
            logging.info("Repository analysis completed.")
        else:
            repo_pipeline.test_repos()
            valid_count = len(repo_pipeline.valid_repos)
            logging.info(f"Found {valid_count} valid repositories.")

    def _commits(self) -> None:
        logging.info("Gathering and filtering commits...")
        repos = RepositoryPipeline(self.config).get_repos()
        logging.info(f"Found {len(repos)} repositories for commit filtering.")
        if not repos:
            logging.warning("No repositories found for commit filtering.")
            return
        
        for repo in repos:
            CommitPipeline(repo, self.config).filter_commits()

    def _testcommits(self) -> None:
        logging.info("Testing commits...")
        tester_pipeline = CommitTesterPipeline(self.config)
        tester_pipeline.test_commit()
        logging.info("Commit testing completed.")

    def _test(self) -> None:
        logging.info("Testing...")
        tester_pipeline = TesterPipeline(self.config)
        tester_pipeline.test()
        logging.info("Testing completed.")
