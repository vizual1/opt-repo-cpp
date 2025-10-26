import os, logging
import src.config as conf
from pathlib import Path

class CommitTester:
    def __init__(self, sha: str = ""):
        self.sha = sha
        self.storage = conf.storage
        Path(self.storage["store_commits"]).mkdir(parents=True, exist_ok=True)
    
    def get_commits(self, repo_id: str) -> tuple[list[tuple[str, str]], str]:
        """Return list of (new_sha, old_sha) pairs and a repo file prefix."""
        try:
            owner, name = repo_id.strip().split("/", 1)
        except ValueError:
            raise ValueError(f"Invalid repo ID format: '{repo_id}'. Expected '<owner>/<repo>'.")

        file_prefix = f"{owner}_{name}"
        filename = (
            f"{file_prefix}_filtered.txt"
            if not self.sha
            else f"{file_prefix}_{self.sha}.txt"
        )
        file_path = Path(self.storage["store_commits"]) / filename

        commits = self._get_filtered_commits(file_path)
        if not commits:
            logging.warning(f"No valid commit pairs found in {file_path}")

        return commits, file_prefix
    
    def get_paths(self, file_prefix: str, sha: str) -> tuple[Path, Path]:
        """
        Returns paths for old/new commit directories to be tested.
        Example: data/commits/<file_prefix>_<sha>/{old,new}
        """
        commit_root = Path(self.storage["store_commits"]) / f"{file_prefix}_{sha}"
        old_path = commit_root / "old"
        new_path = commit_root / "new"
        return old_path, new_path

    def _get_filtered_commits(self, path: Path) -> list[tuple[str, str]]:
        """
        Extract commit pairs from a text file.
        Expected line format:
            <new_sha> | <old_sha> | +<adds> | -<dels> | <total>
        """
        commits_info: list[tuple[str, str]] = []

        if not path.exists():
            logging.warning(f"Commit file not found: {path}")
            return commits_info
        

        try:
            with open(path, 'r', errors='ignore') as f:
                for line_no, line in enumerate(f, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue

                    parts = [p.strip() for p in stripped.split("|") if p.strip()]
                    if len(parts) < 2:
                        logging.warning(f"Malformed commit line at {path}:{line_no} -> {stripped}")
                        continue
                    
                    commits_info.append((parts[0].strip(), parts[1].strip()))

        except (OSError, IOError) as e:
            logging.error(f"Failed to read commits from {path}: {e}", exc_info=True)

        return commits_info