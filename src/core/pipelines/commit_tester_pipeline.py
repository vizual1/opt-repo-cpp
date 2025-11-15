import logging
from tqdm import tqdm
from src.config.config import Config
from src.utils.commit import Commit
from src.gh.crawler import RepositoryCrawler
from src.core.docker.tester import DockerTester

class CommitTesterPipeline:
    """
    This class runs the commits and evaluates its performance.
    """
    def __init__(self, config: Config):
        self.config = config
        self.commit = Commit(self.config.input_file or self.config.storage_paths['commits'])   
        self.docker = DockerTester(self.config) 

    def test_commit(self) -> None:
        if self.config.input_file or self.config.repo_url:
            self._input_tester()
        else:
            self._sha_tester()

    def _input_tester(self) -> None:
        crawler = RepositoryCrawler(self.config)
        repo_ids = crawler.get_repos()  
        if not repo_ids:
            logging.warning("No repositories found for commit testing.")
            return
        
        for repo_id in tqdm(repo_ids, total=len(repo_ids), desc=f"Testing..."):
            try: 
                repo = self.config.git_client.get_repo(repo_id)
                commits, file = self.commit.get_commits(repo.full_name)
                for (new_sha, old_sha) in tqdm(commits, total=len(commits), desc=f"Testing filtered commits..."):
                    try:
                        new_path, old_path = self.commit.get_paths(file, new_sha)
                        self.docker.run_commit_pair(repo, new_sha, old_sha, new_path, old_path)

                    except Exception as e:
                        logging.exception(f"[{repo}] Error testing commits: {e}")

            except Exception as e:
                logging.exception(f"[{repo}] Error testing repository: {e}")

    def _sha_tester(self):
        if self.config.sha:
            commits = self.config.git_client.search_commits(f"hash:{self.config.sha}")
            for commit in commits:
                repo = commit.repository
                if not repo.fork:
                    file = "_".join(repo.full_name.split("/"))
                    commit = repo.get_commit(self.config.sha)
                    new_sha = self.config.sha
                    if not commit.parents:
                        logging.info(f"[{repo.full_name}] Commit {self.config.sha} has no parents (root commit).")
                        return
                    old_sha = commit.parents[0].sha
                    new_path, old_path = self.commit.get_paths(file, new_sha)
                    self.docker.run_commit_pair(repo, new_sha, old_sha, new_path, old_path)
                    break
            
        elif self.config.newsha and self.config.oldsha:
            commits = self.config.git_client.search_commits(f"hash:{self.config.newsha}")
            for commit in commits:
                repo = commit.repository
                if not repo.fork:
                    file = "_".join(repo.full_name.split("/"))
                    new_sha = self.config.newsha
                    old_sha = self.config.oldsha
                    new_path, old_path = self.commit.get_paths(file, new_sha)
                    self.docker.run_commit_pair(repo, new_sha, old_sha, new_path, old_path)
                    break
        else:
            logging.error("Wrong sha input")