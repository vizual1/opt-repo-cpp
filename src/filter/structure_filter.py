import logging, tempfile, os, requests
from collections import Counter
from github import Github
from github.GitTreeElement import GitTreeElement
from typing import Optional

import src.config as conf
from src.cmake.analyzer import CMakeAnalyzer
from src.cmake.process import CMakeProcess
from src.utils.stats import RepoStats
from src.filter.flags_filter import FlagFilter

class StructureFilter:
    """
    This class analyses and filters the structure of a repository.
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

        self.cmake_tree, self.tree_paths, self.tree = self._get_repo_tree()
        self.stats = RepoStats()
        self.testing_flags: dict = {}
        self.process: Optional[CMakeProcess] = None


    def is_valid(self) -> bool:
        vcpkg = self._has_root_vcpkg()
        conan = self._has_root_conan()

        if self._has_root_cmake(): #and (vcpkg or conan):
            logging.info(f"CMakeLists.txt at root ({self.repo.full_name})")

            with tempfile.TemporaryDirectory() as tmpdir:
                self._get_cmake_lists(tmpdir)
                analyzer = CMakeAnalyzer(tmpdir)

                if analyzer.has_testing(nolist=True):
                    logging.info(f"ctest is defined ({self.repo.full_name})")
                    
                    if self._valid_cmake_run(tmpdir, analyzer, vcpkg): #or conan):
                        logging.info(f"cmake and ctest run successfully ({self.repo.full_name})")
                        return True
                    else:
                        logging.warning(f"cmake and ctest failed ({self.repo.full_name})")
                
                else:
                    logging.warning(f"invalid ctest ({self.repo.full_name})")
        else:
            logging.warning(f"no CMakeLists.txt at root ({self.repo.full_name})")

        return False
    
    
    def analyze(self) -> bool:
        if self._has_root_cmake() and (self._has_root_conan() or self._has_root_vcpkg()):
            logging.info(f"CMakeLists.txt and package handler at root ({self.repo.full_name})")

            with tempfile.TemporaryDirectory() as tmpdir:
                self._get_cmake_lists(tmpdir)
                analyzer = CMakeAnalyzer(tmpdir)

                # Analyzing the repository for test structure and flags
                if analyzer.has_testing():
                    logging.info(f"ctest is defined ({self.repo.full_name})")

                    test_dirs = self._extract_test_dirs()
                    if test_dirs:
                        logging.info(f"test directories: {test_dirs}")
                        for d in test_dirs:
                            self.stats.test_dirs[d] += 1
                        conv_test_dir = test_dirs & conf.valid_test_dir

                        if conv_test_dir:
                            logging.info(f"conventional test directories {conv_test_dir}")
                            self.testing_flags = analyzer.has_build_testing_flag()
                            self.test_flags = Counter(self.testing_flags.keys())
                        
                    return True

                    #if self._valid_cmake_run(tmpdir, analyzer):
                    #    logging.info(f"CMake and CTest run successfully: {self.repo.full_name}.")
                    #    return True
                    #else:
                    #    logging.error(f"CMake or CTest failed: {self.repo.full_name}")
                else:
                    logging.error(f"invalid ctest ({self.repo.full_name})")
        else:
            logging.error(f"no CMakeLists.txt or package handler at root ({self.repo.full_name})")
        
        return False
    
    def commit_test(self, sha: str):
        vcpkg = self._has_root_vcpkg()
        conan = self._has_root_conan()

        if self._has_root_cmake(): #and (vcpkg or conan):
            logging.info(f"CMakeLists.txt at root ({self.repo.full_name})")

            #with tempfile.TemporaryDirectory() as tmpdir: # TODO: tmpdir for commits testing?
            self._get_cmake_lists(self.root)
            analyzer = CMakeAnalyzer(self.root)

            if analyzer.has_testing(nolist=True):
                logging.info(f"ctest is defined ({self.repo.full_name})")
                
                if self._valid_cmake_run(self.root, analyzer, vcpkg, sha, test_repeat=3):
                    logging.info(f"cmake and ctest run successfully ({self.repo.full_name})")
                    return True
                else:
                    logging.warning(f"cmake and ctest failed ({self.repo.full_name})")
            
            else:
                logging.warning(f"invalid ctest ({self.repo.full_name})")
        else:
            logging.warning(f"no CMakeLists.txt at root ({self.repo.full_name})")

        return False
    
    def _sort_key(self, y: str) -> tuple[int, int]:
        priority = 0 if any(y.startswith(x) for x in conf.valid_test_dir) else 1
        length = len(y.split("/"))
        return (priority, length)
    
    def _valid_cmake_run(self, root: str, analyzer: CMakeAnalyzer, package_manager: str, sha: str = "", test_repeat: int = 1) -> bool:
        if self.testing_flags:
            flags = FlagFilter(self.testing_flags).get_valid_flags()
        else:
            flags = FlagFilter(analyzer.has_build_testing_flag()).get_valid_flags()

        sorted_testing_path = sorted(analyzer.parser.enable_testing_path, key=self._sort_key)
        if len(sorted_testing_path) == 0:
            logging.info(f"path to enable_testing() was not found: {sorted_testing_path}")
            return False
        enable_testing_path = sorted_testing_path[0].removesuffix("/CMakeLists.txt").removeprefix(root)
        logging.info(f"path to enable_testing(): '{enable_testing_path}'")
        test_path = os.path.join(root, "build", enable_testing_path)
        
        self.process = CMakeProcess(
            root, build=os.path.join(root, "build"), test=test_path, 
            flags=flags, analyzer=analyzer, package_manager=package_manager,
            jobs=4
        )
        if self.process.clone_repo(self.repo_id, root, sha=sha) and self.process.build(): 
            logging.info(f"cmake build was successful ({self.repo.full_name})")
            if self.process.test([], test_repeat=test_repeat):
                logging.info(f"ctest was successful ({self.repo.full_name})")
                return True
            else:
                logging.error(f"ctest failed ({self.repo.full_name})")
        else:
            logging.error(f"cmake build failed ({self.repo.full_name})")
        return False
    
    def _has_root_cmake(self) -> str:
        return self._has_root_file("CMakeLists.txt")
    
    def _has_root_vcpkg(self) -> str:
        return self._has_root_file("vcpkg.json")
    
    def _has_root_conan(self) -> str:
        return self._has_root_file("conanfile.txt") or self._has_root_file("conanfile.py")
    
    def _has_root_bazel(self) -> str:
        return self._has_root_file("WORKSPACE") or self._has_root_file("MODULE.bazel")

    def _has_root_meson(self) -> str:
        return self._has_root_file("meson.build")
    
    def _has_root_file(self, filename: str) -> str:
        """Check whether a repo has <filename> at the root."""
        for item in self.tree:
            if item.type == "blob" and item.path == filename:
                return filename
        return ""

    def _has_test_dir(self) -> bool:
        """Check whether a repository has valid test directories."""
        for item in self.tree_paths:
            for tdir in conf.valid_test_dir:
                if item.startswith(tdir):
                    return True
        return False

    def _get_repo_tree(self) -> tuple[list[GitTreeElement], list[str], list[GitTreeElement]]:
        tree = self.repo.get_git_tree(self.sha, recursive=True).tree
        tree_paths = [item.path for item in tree]
        cmake_tree = [item for item in tree if item.type == "blob" and item.path.endswith("CMakeLists.txt")]
        return cmake_tree, tree_paths, tree
    
    def _get_cmake_lists(self, dest: str) -> list[str]:
        """
        Fetch only CMakeLists.txt files from a GitHub repo using requests, preserving folder structure.
        """
        os.makedirs(dest, exist_ok=True)

        head = self.repo.get_commits()[0]
        sha = head.sha
        owner, name = self.repo.full_name.split("/")
        base_url = f"https://raw.githubusercontent.com/{owner}/{name}/{sha}"

        result_paths = []
        for item in self.cmake_tree:
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