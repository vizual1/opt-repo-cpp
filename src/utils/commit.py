import logging, ast, json
from pathlib import Path
from src.config.config import Config

class Commit:
    def __init__(self, input_file: str, output_path: str):
        self.input_file = input_file
        self.output_path = output_path

    def get_commit_from_input(self, config: Config) -> list[tuple[str, str, str, list[str]]]:
        """
        Return list of (repo_id, new_sha, old_sha, pr_shas) pairs from a given file with docker image names. 
        Each image should be of the form 'owner_repo_newsha'. 
        """
        path = Path(self.input_file)
        images = []
        if path.is_file():
            with open(path, "r", errors="ignore") as f:
                images = [line.strip() for line in f if line.strip()]
        elif path.is_dir():
            images = [p.stem for p in path.glob("*.json")]
            return self.get_commits_from_json_files()
        else:
            raise ValueError(f"Invalid input path: {self.input_file}")

        commits_info: list[tuple[str, str, str, list[str]]] = []
        for image in images: 
            split = tuple(image.split("_"))
            assert len(split) == 3
            owner, repo_name, new_sha = split
            repo_id = f"{owner}/{repo_name}"
            repo = config.git_client.get_repo(repo_id)
            old_sha = repo.get_commit(new_sha.strip().removesuffix(".tar")).parents[0].sha
            commits_info.append((repo_id, new_sha.strip(), old_sha.strip(), []))
        return commits_info

    def get_commits_from_json_files(self) -> list[tuple[str, str, str, list[str]]]:
        """
        Return list of (repo_id, new_sha, old_sha, pr_shas) pairs from
        json files generated from '--testcommits' flag. 
        """
        commits_info: list[tuple[str, str, str, list[str]]] = []
        json_folder = Path(self.input_file)
        for json_file in json_folder.glob("*.json"):
            with open(json_file, 'r', errors='ignore') as f:
                res = json.load(f)

            metadata = res['metadata']
            commit_info = res['commit_info']
            repo_id = metadata['repository_name']
            new_sha = commit_info['new_sha']
            old_sha = commit_info['old_sha']
            commits_info.append((repo_id, new_sha.strip(), old_sha.strip(), []))
        
        return commits_info
    
    def get_commits(self) -> list[tuple[str, str, str, list[str]]]:
        """Return list of (repo_id, new_sha, old_sha, pr_shas) pairs."""
        file_path = Path(self.input_file)

        commits = self._get_filtered_commits(file_path)
        if not commits:
            logging.warning(f"No valid commit pairs found in {file_path}")

        return commits
    
    def get_paths(self, file_prefix: str, sha: str, patch: bool = False) -> tuple[Path, Path]:
        """
        Returns paths for {old,new|patch} commit directories to be tested.
        Example: data/commits/<file_prefix>_<sha>/{old,new|patch}
        """
        output = Path(self.output_path)
        output.chmod(0o777)
        commit_root = output / f"{file_prefix}_{sha}"
        old_path = commit_root / "old"
        new_path = commit_root / "new" if not patch else commit_root / "patch"
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