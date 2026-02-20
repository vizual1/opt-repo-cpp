
import logging
from src.core.pipelines.pipeline import (
    CollectionPipeline, 
    RepositoryPipeline, 
    CommitPipeline, 
    CommitTesterPipeline,
    PushPipeline,
    PatchPipeline
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

            if self.config.testcommits or self.config.genimages:
                self._testcommits()

            if self.config.genimages:
                self._genimages()

            if self.config.pushimages:
                self._pushimages()

            if self.config.testdocker:
                self.config.genimages = False
                self._testdocker()

            if self.config.patch:
                self._patch()

            if self.config.testpatch:
                self.config.genimages = False
                self._testpatch()

            if not any([
                self.config.collect, self.config.testcollect, 
                self.config.commits, self.config.testcommits, 
                self.config.genimages, self.config.testdocker, 
                self.config.patch, self.config.testpatch
            ]):
                logging.warning("No operation selected. Use --collect, --testcollect, --commits, --testcommits, --genimages, --testdocker, --patch or --testpatch")
                
        except Exception as e:
            logging.error(f"Controller encountered an error: {e}", exc_info=True)
            raise

        finally:
            logging.info("Controller execution completed.")

    def _collect(self) -> None:
        logging.info("Collecting popular GitHub repositories...")
        pipeline = CollectionPipeline(self.config)
        repos = pipeline.query_popular_repos()
        logging.info(f"Collected {len(repos)} repositories.")

        if self.config.test:
            logging.info("Testing and validating GitHub repositories...")
            repo_pipeline = RepositoryPipeline(self.config)
            repo_pipeline.test_repos(repos)
            valid_count = len(repo_pipeline.valid_repos)
            logging.info(f"Collected {valid_count} valid repositories.")

    def _testcollect(self) -> None:
        logging.info("Testing and validating GitHub repositories...")
        repo_pipeline = RepositoryPipeline(self.config)
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
        
        commit_pipeline = CommitPipeline(repo_ids, self.config)
        commit_pipeline.filter_all_commits()
        
        if self.config.test:
            filtered_commits = commit_pipeline.filtered_commits
            logging.info("Testing commits...")
            tester_pipeline = CommitTesterPipeline(self.config)
            tester_pipeline.test_commit(filtered_commits)
            logging.info("Commit testing completed.")

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

    def _pushimages(self) -> None:
        logging.info("Pushing docker images to GHCR...")
        push_pipeline = PushPipeline(self.config)
        push_pipeline.push()
        logging.info("Docker images pushed to GHCR.")

    def _testdocker(self) -> None:
        logging.info("Testing docker images...")
        tester_pipeline = CommitTesterPipeline(self.config)
        tester_pipeline.test_commit()
        logging.info("Testing docker images completed.")

    def _patch(self) -> None:
        logging.info("Patching commit...")
        patch_pipeline = PatchPipeline(self.config)
        patch_pipeline.patch()
        logging.info("Commit patched.")

    def _testpatch(self) -> None:
        logging.info("Testing patched docker images...")
        image_pipeline = CommitTesterPipeline(self.config)
        image_pipeline.test_commit()
        logging.info("Testing patched docker images completed.")