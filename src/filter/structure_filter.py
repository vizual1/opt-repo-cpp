import logging, tempfile, os, requests
from collections import Counter
from github import Github
from github.GitTreeElement import GitTreeElement

import src.config as conf
from src.cmake.analyzer import CMakeAnalyzer
from src.cmake.process import CMakeProcess
from src.utils.stats import RepoStats

class StructureFilter:
    """
    This class checks the structure of a repository.
    """
    def __init__(self, repo_id: str, git: Github, root: str = "", sha: str = ""):
        self.repo_id = repo_id
        self.git = git
        self.repo = self.git.get_repo(self.repo_id)
        self.root = root

        if root:
            self.analyzer = CMakeAnalyzer(self.root)

        if sha:
            self.sha = sha
        else:
            self.sha = self.repo.get_commits()[0].sha

        self.cmake_files, self.tree_paths, self.tree = self._get_repo_tree()
        self.stats = RepoStats()


    def is_valid(self) -> bool:
        if self._has_root_cmake(self.cmake_files):
            logging.info(f"CMake at root found in GitHub repository {self.repo.full_name}.")

            if self._has_test_dir(self.tree_paths):
                logging.info(f"Valid test directory found in GitHub repository {self.repo.full_name}.")

                with tempfile.TemporaryDirectory() as tmpdir:
                    if not self.root:
                        self._get_cmakelists(tmpdir)
                        self.analyzer = CMakeAnalyzer(tmpdir)
                    
                    if self.analyzer.has_testing():
                        logging.info(f"CTest found in GitHub repository {self.repo.full_name}.")
                        return self._valid_cmake_run(tmpdir, self.analyzer)
                    else:
                        logging.info(f"No CTest found in GitHub repository {self.repo.full_name}.")
            else:
                logging.info(f"Not a valid test directory structure in GitHub repository {self.repo.full_name}.")
        else:
            logging.info(f"No CMake at root found in GitHub repository {self.repo.full_name}.")

        return False
    
    
    def analyze(self) -> bool:
        if self._has_root_cmake(self.cmake_files):
            logging.info(f"CMake at root found in GitHub repository {self.repo.full_name}.")

            with tempfile.TemporaryDirectory() as tmpdir:
                
                self._get_cmakelists(tmpdir)
                analyzer = CMakeAnalyzer(tmpdir)

                # Analyzing the repository for test structure and flags
                if analyzer.has_testing():
                    logging.info(f"add_test and enable_testing in GitHub repository {self.repo.full_name}.")
                    
                    test_dirs = self._extract_test_dirs()
                    if test_dirs:
                        logging.info(f"Test directories: {test_dirs} in GitHub repository {self.repo.full_name}")
                        for d in test_dirs:
                            self.stats.test_dirs[d] += 1
                        conv_test_dir = test_dirs & conf.TEST_DIR

                        if conv_test_dir:
                            logging.info(f"Repo {self.repo.full_name} has conventional test dirs: {conv_test_dir}")
                            self.test_flags = Counter(analyzer.has_build_testing_flag().keys())
                        
                        if self._valid_cmake_run(tmpdir, analyzer):
                            logging.info(f"CMake and CTest run successfully: {self.repo.full_name}.")
                            return True
                else:
                    logging.info(f"No CTest found in GitHub repository {self.repo.full_name}.")
        else:
            logging.info(f"No CMake at root found in GitHub repository {self.repo.full_name}.")
        
        return False
    
    
    def _valid_cmake_run(self, root: str, analyzer: CMakeAnalyzer) -> bool:
        enable_testing_path = analyzer.parser.enable_testing_path.removesuffix("/CMakeLists.txt").removeprefix(root)
        test_path = os.path.join(root, "build", enable_testing_path)
        process = CMakeProcess(root, os.path.join(root, "build"), test_path, analyzer=analyzer)
        if process.clone_repo(self.repo_id, root) and process.build(): 
            logging.info(f"Building {self.repo.full_name} was successful.")
            if process.test():
                logging.info(f"Testing {self.repo.full_name} was successful.")
                return True
            else:
                logging.info(f"Testing {self.repo.full_name} failed.")
        else:
            logging.info(f"Building {self.repo.full_name} failed.")
            
        return False
    
    def _has_root_cmake(self, cmake_files: list[GitTreeElement]) -> bool:
        """Check whether a repo has a CMakeLists.txt at the root."""
        for item in cmake_files:
            if item.type == "blob" and item.path == "CMakeLists.txt":
                return True
        return False

    def _has_test_dir(self, tree_paths: list[str]) -> bool:
        """Check whether a repository has valid test directories."""
        for item in tree_paths:
            for tdir in conf.TEST_DIR:
                if item.startswith(tdir):
                    return True
        return False

    def _get_repo_tree(self) -> tuple[list[GitTreeElement], list[str], list[GitTreeElement]]:
        tree = self.repo.get_git_tree(self.sha, recursive=True).tree
        tree_paths = [item.path for item in tree]
        cmake_files = [item for item in tree if item.type == "blob" and item.path.endswith("CMakeLists.txt")]
        return cmake_files, tree_paths, tree
    
    def _get_cmakelists(self, dest: str) -> list[str]:
        """
        Fetch only CMakeLists.txt files from a GitHub repo using requests, preserving folder structure.
        """
        os.makedirs(dest, exist_ok=True)

        head = self.repo.get_commits()[0]
        sha = head.sha
        owner, name = self.repo.full_name.split("/")
        base_url = f"https://raw.githubusercontent.com/{owner}/{name}/{sha}"

        result_paths = []
        for item in self.cmake_files:
            url = f"{base_url}/{item.path}"
            try:
                r = requests.get(url)
                r.raise_for_status()

                target_path = os.path.join(dest, item.path)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "wb") as f:
                    f.write(r.content)

                result_paths.append(target_path)
            except requests.exceptions.RequestException as e:
                logging.warning(f"Error fetching {url}: {e}")
            except (OSError, IOError) as e:
                logging.error(f"Failed to write {target_path}: {e}", exc_info=True)

        return result_paths

    def _extract_test_dirs(self) -> set[str]:
        """Extracts all directories that look like test directories from a PyGithub GitTree."""
        test_dirs: set[str] = set()

        for element in self.tree: 
            path = element.path.lower()
            parts = path.split("/")

            for i, part in enumerate(parts[:-1]):
                if any(keyword in part for keyword in conf.TEST_KEYWORDS):
                    test_dir = "/".join(parts[:i+1])
                    test_dirs.add(test_dir)

        top_level_dirs: set[str] = set()
        for dir_path in test_dirs:
            if not any(dir_path != other and dir_path.startswith(other + "/") for other in test_dirs):
                top_level_dirs.add(dir_path)

        return top_level_dirs
