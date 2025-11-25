import logging
from pathlib import Path

class Commit:
    def __init__(self, input_path: str):
        self.input_path = input_path
        Path(self.input_path).mkdir(parents=True, exist_ok=True)
    
    # repo_id: str
    def get_commits(self) -> list[tuple[str, str, str]]:
        """Return list of (repo_id, new_sha, old_sha) pairs."""
        #try:
        #    owner, name = repo_id.strip().split("/", 1)
        #except ValueError:
        #    raise ValueError(f"Invalid repo ID format: '{repo_id}'. Expected '<owner>/<repo>'.")
        
        #file_prefix = f"{owner}_{name}"
        #filename = f"{file_prefix}_filtered.txt"
        file_path = Path(self.input_path) #/ filename

        commits = self._get_filtered_commits(file_path)
        if not commits:
            logging.warning(f"No valid commit pairs found in {file_path}")

        return commits
    
    def get_paths(self, file_prefix: str, sha: str) -> tuple[Path, Path]:
        """
        Returns paths for {old,new} commit directories to be tested.
        Example: data/commits/<file_prefix>_<sha>/{old,new}
        """
        output = Path(self.input_path)
        output.chmod(0o777)
        commit_root = output / f"{file_prefix}_{sha}"
        old_path = commit_root / "old"
        new_path = commit_root / "new"
        return new_path, old_path

    def _get_filtered_commits(self, path: Path) -> list[tuple[str, str, str]]:
        """
        Extract commit pairs from a text file.
        Expected line format:
            <new_sha> | <old_sha> | ...
        """
        commits_info: list[tuple[str, str, str]] = []

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
                    if len(parts) <= 2:
                        logging.warning(f"Malformed commit line at {path}:{line_no} -> {stripped}")
                        continue

                    if len(parts) > 2:
                        # repo_id | new_sha | old_sha
                        commits_info.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))

        except (OSError, IOError) as e:
            logging.error(f"Failed to read commits from {path}: {e}", exc_info=True)

        return commits_info

    def get_file_prefix(self, repo_id: str) -> str:
        try:
            owner, name = repo_id.strip().split("/", 1)
        except ValueError:
            raise ValueError(f"Invalid repo ID format: '{repo_id}'. Expected '<owner>/<repo>'.")
        
        return f"{owner}_{name}"