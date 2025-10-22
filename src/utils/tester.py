import os, logging
import src.config as conf
from pathlib import Path

class CommitTester:
    def __init__(self, sha: str = ""):
        self.sha = sha
        self.storage = conf.storage
    
    def get_commits(self, repo_id: str) -> tuple[list[tuple[str, str]], str]:
        repo_info = repo_id.split("/")
        owner = repo_info[0].strip()
        name = repo_info[1].strip()
        file = f"{owner}_{name}"
        if not self.sha:
            commits = self._get_filtered_commits(Path(self.storage['store_commits'], f"{file}_filtered.txt"))
        else:
            commits = self._get_filtered_commits(Path(self.storage['store_commits'], f"{file}_{self.sha}.txt"))
        return commits, file
    
    def get_paths(self, file: str, sha: str) -> tuple[Path, Path]:
        commit_path = os.path.join(self.storage['store_commits'], f"{file}_{sha}")
        old_path = Path(commit_path, "old")
        new_path = Path(commit_path, "new")
        return old_path, new_path

    def _get_filtered_commits(self, path: Path) -> list[tuple[str, str]]:
        """Extract commit information from a file."""
        commits_info: list[tuple[str, str]] = []
        try:
            with open(path, 'r', errors='ignore') as f:
                for line in f:
                    if not line.strip():
                        continue
                    parts = line.split("|")
                    if len(parts) >= 2:
                        commits_info.append((parts[0].strip(), parts[1].strip()))
                    else:
                        logging.warning(f"Malformed commit line: {line.strip()}")
                        break
        except (OSError, IOError) as e:
            logging.error(f"Failed to read {path}: {e}", exc_info=True)

        return commits_info