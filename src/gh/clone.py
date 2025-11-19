import os, stat, subprocess, shutil, logging
from pathlib import Path

class GitHandler:
    def _get_default_branch(self, repo_url: str) -> str:
        result = subprocess.run(
            ["git", "ls-remote", "--symref", repo_url, "HEAD"],
            capture_output=True, text=True
        )

        for line in result.stdout.splitlines():
            if line.startswith("ref:"):
                return line.split()[1].split("/")[-1]
        return "main" 

    def clone_repo(self, repo_id: str, repo_path: Path, branch: str = "main", sha: str = "") -> bool:
        url = f"https://github.com/{repo_id}.git"
        
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path, onerror=self._on_rm_error)

        repo_path.mkdir(parents=True, exist_ok=True)
        
        if sha:
            logging.info(f"Cloning repository {url} for commit {sha} into {repo_path}")
            try:
                subprocess.run(
                    ["git", "config", "--local", "safe.directory", str(repo_path)],
                    cwd=repo_path,
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                subprocess.run(
                    ["git", "clone", "--depth=1", url, repo_path],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                subprocess.run(
                    ["git", "fetch", "--depth=1", "origin", sha],
                    cwd=repo_path,
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                subprocess.run(
                    ["git", "checkout", sha],
                    cwd=repo_path,
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                
                subprocess.run(
                    ["git", "submodule", "update", "--init", "--recursive", "--depth=1"],
                    cwd=repo_path,
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                self.set_permission(str(repo_path))
                logging.info(f"Repository checked out to commit {sha} successfully")
                return True
                
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to clone/checkout commit {sha}", exc_info=True)
                logging.error(f"Output (stdout):\n{e.stdout}")
                logging.error(f"Error (stderr):\n{e.stderr}")
                return False

        if branch == "main":
            branch = self._get_default_branch(url)
        
        logging.info(f"Cloning repository {url} (branch: {branch}) into {repo_path}")
        try:
            result = subprocess.run(
                ["git", "clone", "--recurse-submodules", "--shallow-submodules", 
                 "--branch", branch, "--depth=1", url, repo_path], 
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            logging.info(f"Repository cloned successfully")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to clone repository {url} (branch: {branch})", exc_info=True)
            logging.error(f"Output (stdout):\n{e.stdout}")
            logging.error(f"Error (stderr):\n{e.stderr}")
            return False
        
    def _on_rm_error(self, func, path, exc_info):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    
    def set_permission(self, path: str):
        for root, dirs, files in os.walk(path):
            os.chmod(root, 0o777)
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o777)
            for f in files:
                os.chmod(os.path.join(root, f), 0o777)