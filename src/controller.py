
import logging
#from src.docker.generator import DockerBuilder
from src.pipeline import RepositoryPipeline, CommitPipeline, TesterPipeline
from src.utils.dataclasses import Config

class Controller:
    """
    This class builds a Controller to crawl, filter, download, build Dockerfiles or test GitHub repositories.
    """
    def __init__(self, config: Config, url: str = "", sha: str = ""):
        self.url = url
        self.sha = sha
        self.config = config

    def run(self):
        logging.info("Starting controller...")

        try:
            if self.config.crawl:
                self._crawl()

            if self.config.test:
                self._tester()

            if self.config.docker:
                self._docker()

            if not any([self.config.crawl, self.config.test, self.config.docker]):
                logging.warning("No operation selected. Use --crawl, --test, or --docker.")

        except Exception as e:
            logging.error(f"Controller encountered an error: {e}", exc_info=True)

        finally:
            logging.info("Controller execution completed.")
        
    def _crawl(self):
        logging.info("Crawling GitHub repositories...")

        repo_pipeline = RepositoryPipeline(self.url, self.config)

        if self.config.analyze:
            repo_pipeline.analyze_repos()
            logging.info("Repository analysis completed.")
            return

        repo_pipeline.get_repos()
        logging.info(f"Found {len(repo_pipeline.valid_repos)} valid repositories.")

        if self.config.commits and repo_pipeline.valid_repos:
            for repo in repo_pipeline.valid_repos:
                try:
                    commit_pipeline = CommitPipeline(repo=repo, sha=self.sha, config=self.config)
                    commit_pipeline.get_commits()
                except Exception as e:
                    logging.error(f"Failed to process commits for {repo.full_name}: {e}", exc_info=True)
            logging.info("Commit processing completed.")

    def _tester(self):
        logging.info("Testing commits...")
        
        try:
            tester_pipeline = TesterPipeline(url=self.url, sha=self.sha, config=self.config)
            tester_pipeline.test_commit()
            logging.info("Testing completed successfully.")
        except Exception as e:
            logging.error(f"Testing failed: {e}", exc_info=True)

    def _docker(self):
        #docker = DockerBuilder()
        #docker.create()
        logging.info("Building Docker image...")
        raise NotImplementedError("Docker pipeline is not yet implemented.")




