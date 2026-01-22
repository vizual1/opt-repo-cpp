import logging, subprocess, docker
from src.config.config import Config
from src.utils.commit import Commit
from src.utils.image_handling import image_exists, image

class PushPipeline():
    def __init__(self, config: Config):
        self.config = config
        self.commit = Commit(self.config.input_file or self.config.storage_paths['commits'], self.config.storage_paths['clones'])

    def push(self) -> None:
        if self.config.input:
            commits = self.commit.get_commits_from_json_files()
            self._push_commits(commits)
        else:
            logging.warning(f"Invalid input: {self.config.input}")
    
    def _push_commits(self, commits: list[tuple[str, str, str, list[str]]]) -> None:
        for i, (repo_id, new_sha, old_sha, pr_shas) in enumerate(commits):
            local_image = image(repo_id, new_sha)
            if not self.config.dockerhub_force and local_image in self.config.dockerhub_containers:
                continue
            remote_image = f"{self.config.dockerhub_user}/{self.config.dockerhub_repo}:{local_image}"
            if image_exists(repo_id, new_sha) and (not image_exists(other=remote_image) or self.config.dockerhub_force):
                logging.info(f"Tagging {local_image} -> {remote_image}")
                subprocess.run(["docker", "tag", local_image, remote_image], check=True)
                logging.info(f"Pushing {remote_image} to Dockerhub")
                subprocess.run(["docker", "push", remote_image], check=True)
            
            
            
