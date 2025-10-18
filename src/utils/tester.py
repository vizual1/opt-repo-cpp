import os, logging
import src.config as conf
from src.cmake.process import CMakeProcess
from src.cmake.analyzer import CMakeAnalyzer
from src.filter.flags_filter import FlagFilter

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
            commits = self._get_filtered_commits(os.path.join(self.storage['store_commits'], f"{file}_filtered.txt"))
        else:
            commits = self._get_filtered_commits(os.path.join(self.storage['store_commits'], f"{file}_{self.sha}.txt"))
        return commits, file
    
    def get_paths(self, file: str, sha: str) -> tuple[str, str]:
        commit_path = os.path.join(self.storage['store_commits'], f"{file}_{sha}")
        parent_path = os.path.join(commit_path, "parent")
        current_path = os.path.join(commit_path, "current")
        return parent_path, current_path
    
    def create_process(self, analyzer: CMakeAnalyzer, path: str) -> CMakeProcess:
        enable_testing_path = analyzer.parser.enable_testing_path[0].removesuffix("/CMakeLists.txt").removeprefix(path)
        build_path = os.path.join(path, "build")
        test_path = os.path.join(path, "build", enable_testing_path)
        flags = FlagFilter(analyzer.has_build_testing_flag()).get_valid_flags()
        return CMakeProcess(path, build_path, test_path, flags=flags, analyzer=analyzer, package_manager="")

    def _get_filtered_commits(self, path: str) -> list[tuple[str, str]]:
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