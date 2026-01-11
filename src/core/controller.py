
import logging
from src.core.pipelines.pipeline import (
    CollectionPipeline, 
    RepositoryPipeline, 
    CommitPipeline, 
    CommitTesterPipeline,
    PatchingPipeline
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
    """
    def __init__(self, config: Config):
        self.config = config

    def run(self) -> None:
        logging.info("Starting controller...")

        try:
            if self.config.collect:
                self._collect()
            
            if self.config.testcollect:
                self._testcollect()

            if self.config.commits:
                self._commits()

            if self.config.testcommits:
                self._testcommits()

            if self.config.genimages:
                self._genimages()

            if self.config.testdocker:
                self.config.genimages = False
                self._testdocker()
            
            if self.config.patch:
                self._patch()

            if self.config.testdockerpatch:
                self.config.genimages = False
                self._testdockerpatch()

            if not any([
                self.config.collect, self.config.testcollect, 
                self.config.commits, self.config.testcommits, 
                self.config.genimages, self.config.testdocker, 
                self.config.patch, self.config.testdockerpatch
            ]):
                logging.warning("No operation selected. Use --collect, --testcollect, --commits, --testcommits, --genimages, --patch, --testdocker or --testdockerpatch")
                
        except Exception as e:
            logging.error(f"Controller encountered an error: {e}", exc_info=True)

        finally:
            logging.info("Controller execution completed.")

    def _collect(self) -> None:
        logging.info("Collecting popular GitHub repositories...")
        pipeline = CollectionPipeline(self.config)
        pipeline.query_popular_repos()
        logging.info("Popular repository colelction completed.")
        
    def _testcollect(self) -> None:
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
        repo_ids = RepositoryPipeline(self.config).get_repos()
        logging.info(f"Found {len(repo_ids)} repositories for commit filtering.")
        if not repo_ids:
            logging.warning("No repositories found for commit filtering.")
            return
        
        CommitPipeline(repo_ids, self.config).filter_all_commits()

    def _testcommits(self) -> None:
        logging.info("Testing commits...")
        tester_pipeline = CommitTesterPipeline(self.config)
        tester_pipeline.test_commit()
        logging.info("Commit testing completed.")

    def _genimages(self) -> None:
        logging.info("Generating Docker Images...")
        image_pipeline = CommitTesterPipeline(self.config)
        image_pipeline.test_commit()
        logging.info("Docker images generated.")

    def _testdocker(self) -> None:
        logging.info("Testing docker images...")
        tester_pipeline = CommitTesterPipeline(self.config)
        tester_pipeline.test_commit()
        logging.info("Testing docker images completed.")

    def _patch(self) -> None:
        logging.info("Patching docker images...")
        #patching_pipeline = PatchingPipeline(self.config)
        #patching_pipeline.patch_all()
        logging.info("Patching docker images completed.")

    def _testdockerpatch(self) -> None:
        logging.info("Testing patched docker images...")
        image_pipeline = CommitTesterPipeline(self.config)
        image_pipeline.test_commit()
        logging.info("Testing patched docker images completed.")