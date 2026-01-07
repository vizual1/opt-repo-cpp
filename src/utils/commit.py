import logging, ast
from pathlib import Path

class Commit:
    def __init__(self, input_file: str, output_path: str):
        self.input_file = input_file
        self.output_path = output_path
    
    def get_commits(self) -> list[tuple[str, str, str, list[str]]]:
        """Return list of (repo_id, new_sha, old_sha, pr_shas) pairs."""
        file_path = Path(self.input_file)

        commits = self._get_filtered_commits(file_path)
        if not commits:
            logging.warning(f"No valid commit pairs found in {file_path}")

        return commits
    
    def get_paths(self, file_prefix: str, sha: str) -> tuple[Path, Path]:
        """
        Returns paths for {old,new} commit directories to be tested.
        Example: data/commits/<file_prefix>_<sha>/{old,new}
        """
        output = Path(self.output_path)
        output.chmod(0o777)
        commit_root = output / f"{file_prefix}_{sha}"
        old_path = commit_root / "old"
        new_path = commit_root / "new"
        return new_path, old_path

    def _get_filtered_commits(self, path: Path) -> list[tuple[str, str, str, list[str]]]:
        """
        Extract commit pairs from a text file.
        Expected line format:
            <repo_id> | <new_sha> | <old_sha> | [<new_sha_not_pr>, ...] | ...
        """
        commits_info: list[tuple[str, str, str, list[str]]] = []

        if not path.exists():
            logging.warning(f"Commit file not found: {path}")
            return commits_info
        
        try:
            with open(path, 'r', errors='ignore') as f:
                for line_no, line in enumerate(f, start=1):
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue

                    parts = [p.strip() for p in stripped.split("|") if p.strip()]
                    if len(parts) < 3:
                        logging.warning(f"Malformed commit line at {path}:{line_no} -> {stripped}")
                        continue

                    repo_id = parts[0]
                    new_sha = parts[1]
                    old_sha = parts[2]

                    if len(parts) > 3:
                        try:
                            extra_commits = ast.literal_eval(parts[3])
                            if not isinstance(extra_commits, list):
                                raise ValueError("Expected list")
                        except Exception as e:
                            logging.warning(f"Invalid commit list at {path}:{line_no} -> {parts[3]} ({e})")
                            extra_commits = []
                    else:
                        extra_commits = []
                    
                    commits_info.append((repo_id, new_sha, old_sha, extra_commits))


        except (OSError, IOError) as e:
            logging.error(f"Failed to read commits from {path}: {e}", exc_info=True)

        return commits_info

    def get_file_prefix(self, repo_id: str) -> str:
        try:
            owner, name = repo_id.strip().split("/", 1)
        except ValueError:
            raise ValueError(f"Invalid repo ID format: '{repo_id}'. Expected '<owner>/<repo>'.")
        
        return f"{owner}_{name}"