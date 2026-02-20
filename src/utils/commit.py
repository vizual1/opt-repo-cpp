import logging, ast, json
from pathlib import Path
from src.config.config import Config
from github.Commit import Commit

class CommitHandler:
    def __init__(self, input_file: str, output_path: str):
        self.input_file = input_file
        self.output_path = output_path

    def _get_commits_from_json_files(self) -> list[tuple[str, str, str]]:
        """
        Return list of (repo_id, new_sha, old_sha) pairs from
        json files generated from '--testcommits' flag. 
        """
        commits_info: list[tuple[str, str, str]] = []
        json_folder = Path(self.input_file)
        for json_file in json_folder.glob("*.json"):
            with open(json_file, 'r', errors='ignore') as f:
                res = json.load(f)

            metadata = res['metadata']
            commit_info = res['commit_info']
            repo_id = metadata['repository_name']
            new_sha = commit_info['new_sha']
            old_sha = commit_info['old_sha']
            commits_info.append((repo_id, new_sha.strip(), old_sha.strip()))
        
        return commits_info
    
    def get_commits(self, commits_list: list[Commit] = []) -> list[tuple[str, str, str]]:
        """Return list of (repo_id, new_sha, old_sha) pairs."""
        file_path = Path(self.input_file)

        if commits_list:
            all_commits = [(commit.repository.full_name, commit.sha, commit.parents[0].sha) for commit in commits_list]
        elif file_path.is_file():
            all_commits = self._get_filtered_commits(file_path)
        elif file_path.is_dir():
            all_commits = self._get_commits_from_json_files()

        if not all_commits:
            logging.warning(f"No valid commit pairs found in {file_path}")

        return all_commits
    
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

    def _get_filtered_commits(self, path: Path) -> list[tuple[str, str, str]]:
        """
        Extract commit pairs from a text file.
        Expected line format:
            <repo_id> | <new_sha> | <old_sha>
        """
        commits_info: list[tuple[str, str, str]] = []

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
                    
                    commits_info.append((repo_id, new_sha, old_sha))

        except (OSError, IOError) as e:
            logging.error(f"Failed to read commits from {path}: {e}", exc_info=True)

        return commits_info

    def get_file_prefix(self, repo_id: str) -> str:
        try:
            owner, name = repo_id.strip().split("/", 1)
        except ValueError:
            raise ValueError(f"Invalid repo ID format: '{repo_id}'. Expected '<owner>/<repo>'.")
        
        return f"{owner}_{name}"