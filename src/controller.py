
import logging
from src.docker.generator import DockerBuilder
from src.pipeline import RepositoryPipeline, CommitPipeline, TesterPipeline
from src.utils.dataclasses import Config

class Controller:
    """
    This class builds a Controller to crawl, filter, download, build Dockerfiles or test GitHub repositories.
    """
    def __init__(self, config: Config, crawl: bool = False, test: bool = False, docker: bool = False, 
                 url: str = "", sha: str = ""):
        self.crawl, self.test, self.docker = crawl, test, docker
        self.url, self.sha = url, sha
        self.config = config

    def run(self):
        if self.crawl:
            logging.info("Crawling GitHub repositories...")
            self._crawl()
        if self.test:
            logging.info("Testing commits...")
            self._tester()
        if self.docker:
            logging.info("Building Dockerfile...")
            self._docker()
        
    def _crawl(self):
        repo_pipeline = RepositoryPipeline(self.url, self.config)
        if self.config.analyze:
            repo_pipeline.analyze_repos()
        else:
            repo_pipeline.get_repos()
            #valid_repos = repo_pipeline.valid_repos
            # TODO: put that under TESTER
            #for repo in valid_repos:
            #    commit_pipeline = CommitPipeline(repo=repo, sha=self.sha, config=self.config)
            #    commit_pipeline.get_commits()

    def _tester(self):
        tester_pipeline = TesterPipeline(url=self.url, sha=self.sha, config=self.config)
        if self.config.test_commit:
            tester_pipeline.test_commit()
        elif self.config.test_configure:
            tester_pipeline.test_configure()
        elif self.config.test_build:
            tester_pipeline.test_build()
        elif self.config.test_ctest:
            tester_pipeline.test_ctest()

    def _docker(self):
        docker = DockerBuilder()
        docker.create()





