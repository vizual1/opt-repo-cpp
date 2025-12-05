import logging
from tqdm import tqdm
from src.config.config import Config
from src.utils.commit import Commit
from src.core.docker.tester import DockerTester

class CommitTesterPipeline:
    """
    This class runs the commits and evaluates its performance.
    """
    def __init__(self, config: Config):
        self.config = config
        self.commit = Commit(self.config.input_file or self.config.storage_paths['commits'], self.config.storage_paths['clones'])   
        self.docker = DockerTester(self.config) 

    def test_commit(self) -> None:
        if self.config.input_file or self.config.repo_id:
            self._input_tester()
        else:
            self._sha_tester()

    def _input_tester(self) -> None:
        commits = self.commit.get_commits()
        for repo_id, new_sha, old_sha in tqdm(commits, total=len(commits), desc="Commits testing...", position=0):
            file = self.commit.get_file_prefix(repo_id)
            new_path, old_path = self.commit.get_paths(file, new_sha)
            try:
                repo = self.config.git_client.get_repo(repo_id)
                self.docker.run_commit_pair(repo, new_sha, old_sha, new_path, old_path)
            except Exception as e:
                logging.exception(f"[{repo_id}] Error testing commits: {e}")

    def _sha_tester(self):
        if self.config.sha and self.config.repo_id:
            repo = self.config.git_client.get_repo(self.config.repo_id)
            commit = repo.get_commit(self.config.sha)
            file_prefix = "_".join(repo.full_name.split("/"))
            new_sha = self.config.sha
            if not commit.parents:
                logging.info(f"[{repo.full_name}] Commit {self.config.sha} has no parents (root commit).")
                return
            old_sha = commit.parents[0].sha
            new_path, old_path = self.commit.get_paths(file_prefix, new_sha)
            self.docker.run_commit_pair(repo, new_sha, old_sha, new_path, old_path)
        else:
            logging.error("Wrong sha input")