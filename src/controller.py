
import logging
from src.docker.generator import DockerBuilder
from src.pipeline import RepositoryPipeline, CommitPipeline, TesterPipeline
from src.utils.dataclasses import Config

class Controller:
    """
    This class builds a Controller to crawl, filter, download, build Dockerfiles or test GitHub repositories.
    """
    def __init__(self, config: Config, url: str = "", sha: str = ""):
        self.url, self.sha = url, sha
        self.config = config

    def run(self):
        if self.config.crawl:
            logging.info("Crawling GitHub repositories...")
            self._crawl()
        if self.config.test:
            logging.info("Testing commits...")
            self._tester()
        if self.config.docker:
            logging.info("Building Dockerfile...")
            self._docker()
        
    def _crawl(self):
        repo_pipeline = RepositoryPipeline(self.url, self.config)
        if self.config.analyze:
            repo_pipeline.analyze_repos()
        else:
            repo_pipeline.get_repos()
            if self.config.commits:
                valid_repos = repo_pipeline.valid_repos
                for repo in valid_repos:
                    commit_pipeline = CommitPipeline(repo=repo, sha=self.sha, config=self.config)
                    commit_pipeline.get_commits()

    def _tester(self):
        tester_pipeline = TesterPipeline(url=self.url, sha=self.sha, config=self.config)
        tester_pipeline.test_commit()

    def _docker(self):
        docker = DockerBuilder()
        docker.create()





