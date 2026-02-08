import uuid, subprocess, logging, shutil
from src.config.config import Config
from src.gh.clone import GitHandler
from src.utils.image_handling import image
from pathlib import Path

class PatchPipeline:
    def __init__(self, config: Config):
        self.config = config
        self.git_handler = GitHandler()

    def patch(self) -> None:
        unique_id = str(uuid.uuid4())
        name = "-".join(self.config.repo_id.split("/"))
        path = Path(f"tmp/patch_{unique_id}").resolve()
        patch_data = Path("data/patch").resolve()
        logging.info(f"Path: {path}, {patch_data}")
        path.mkdir(mode=0o777, parents=True, exist_ok=True)
        patch_data.mkdir(mode=0o777, parents=True, exist_ok=True)

        cmd = [
            "docker", "run", "--rm", "-i", "--pull=always",
            "-e", f"SANDBOX_RUNTIME_CONTAINER_IMAGE={self.config.llm.sandbox_base_container_image}",
            "-e", f"SANDBOX_VOLUMES={patch_data}:/results:rw,{path}:/workspace:rw",
            "-e", f"LLM_API_KEY={self.config.llm.api_key}",
            "-e", f"LLM_MODEL={self.config.llm.model}",
            "-e", f"LLM_BASE_URL={self.config.llm.base_url}",
            "-e", f"GITHUB_TOKEN={self.config.github.access_token}",
            "-e", "LOG_ALL_EVENTS=true",
            "-v", f"{self.config.llm.docker_socket}:/var/run/docker.sock",
            "--add-host", "host.docker.internal:host-gateway",
            "--name", f"openhands-cli-{unique_id}-{name}",
            self.config.llm.openhands_model,
            "python", "-m", "openhands.core.main", "-t",
            self.config.prompt
        ]
        logging.info(f"Patching the commit of {self.config.repo_id} ({self.config.sha})")
        
        # move .git
        git_dir = path / ".git"
        temp_git_dir = path.parent / f".git_temp_{unique_id}"
        try:
            repo = self.config.git_client.get_repo(self.config.repo_id)
            commit = repo.get_commit(self.config.sha)
            parent_sha = commit.parents[0].sha
            self.git_handler.clone_repo(self.config.repo_id, path, sha=parent_sha)
            if git_dir.exists():
                logging.info("Moving .git directory out of workspace before sandbox run")
                git_dir.rename(temp_git_dir)
            self.run(cmd, self.config.repo_id, self.config.sha)
            if temp_git_dir.exists():
                logging.info("Moving .git directory back into workspace after sandbox run")
                temp_git_dir.rename(git_dir)
            patch_file = patch_data / f"{image(self.config.repo_id, self.config.sha)}.patch"
            with patch_file.open("wb") as f:
                subprocess.run(["git", "diff", "--no-color", "--binary"], cwd=path, check=True, stdout=f)
        finally:
            if temp_git_dir.exists():
                logging.info("Restoring .git directory after cleanup")
                if path.exists():
                    temp_git_dir.rename(path / ".git")
            if path.exists():
                shutil.rmtree(path)
    
    def run(self, cmd: list[str], repo_id: str, sha: str, timeout_seconds=15*60) -> None:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout_seconds)

        if result.returncode != 0:
            logging.error(f"Failed to patch {self.config.repo_id} ({self.config.sha})")
            if result.stdout: logging.error(f"STDOUT:\n{result.stdout}")
            if result.stderr: logging.error(f"STDERR:\n{result.stderr}")
        else:
            if result.stdout: logging.info(f"STDOUT:\n{result.stdout}")