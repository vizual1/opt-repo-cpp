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

    def test_commit(self) -> None:
        if self.config.input_file or self.config.repo_id:
            self._input_tester()
        else:
            self._sha_tester()

    def _input_tester(self) -> None:
        commits = self.commit.get_commits()
        with tqdm(commits, total=len(commits), position=0, mininterval=5) as pbar:
            for repo_id, new_sha, old_sha in pbar:
                pbar.set_description(f"Commits testing {repo_id}")
                file = self.commit.get_file_prefix(repo_id)
                new_path, old_path = self.commit.get_paths(file, new_sha)
                try:
                    repo = self.config.git_client.get_repo(repo_id)
                    docker = DockerTester(repo, self.config)
                    docker.run_commit_pair(new_sha, old_sha, new_path, old_path)
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
            docker = DockerTester(repo, self.config)
            docker.run_commit_pair(new_sha, old_sha, new_path, old_path)
        else:
            logging.error("Wrong sha input")