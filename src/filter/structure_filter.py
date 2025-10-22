import logging, tempfile, os, requests
from collections import Counter
from github import Github
from github.GitTreeElement import GitTreeElement
from typing import Optional
from pathlib import Path

import src.config as conf
from src.cmake.analyzer import CMakeAnalyzer
from src.cmake.process import CMakeProcess
from src.utils.stats import RepoStats
from src.filter.flags_filter import FlagFilter
#from src.docker.generator import DockerBuilder

class StructureFilter:
    """
    This class analyses and filters the structure of a repository.
    """
    def __init__(self, repo_id: str, git: Github, root: Optional[Path] = None, sha: str = ""):
        self.repo_id = repo_id
        self.repo = git.get_repo(self.repo_id)
        self.root = root
        self.sha = sha if sha else self.repo.get_commits()[0].sha

        self.cmake_tree, self.tree_paths, self.tree = self._get_repo_tree()
        self.stats = RepoStats()
        self.testing_flags: dict = {}
        self.process: Optional[CMakeProcess] = None

    def is_valid(self, without_pkg_manager: bool = True) -> bool:
        vcpkg = self._has_root_vcpkg()
        conan = self._has_root_conan()

        if not self._has_root_cmake() or not (without_pkg_manager or vcpkg or conan):
            logging.warning(f"no CMakeLists.txt at root ({self.repo.full_name})")
            return False
        
        logging.info(f"CMakeLists.txt at root ({self.repo.full_name})")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            self._get_cmake_lists(tmpdir)
            analyzer = CMakeAnalyzer(tmpdir)

            if not analyzer.has_testing(nolist=conf.testing['no_list_testing']):
                logging.warning(f"invalid ctest ({self.repo.full_name})")
                return False
            
            test_dirs = self._extract_test_dirs()
            if test_dirs:
                logging.debug(f"test directories: {test_dirs}")
                for d in test_dirs:
                    self.stats.test_dirs[d] += 1
                conv_test_dir = test_dirs & conf.valid_test_dir

                if conv_test_dir:
                    logging.debug(f"conventional test directories {conv_test_dir}")
                    self.testing_flags = analyzer.has_build_testing_flag()
                    self.test_flags = Counter(self.testing_flags.keys())
            
            logging.info(f"ctest is defined ({self.repo.full_name})")
            return True
        
            #if self._valid_cmake_run(tmpdir, analyzer, vcpkg): #or conan):
            #    logging.info(f"cmake and ctest run successfully ({self.repo.full_name})")
            #else:
            #    logging.warning(f"cmake and ctest failed ({self.repo.full_name})")
                
    def is_valid_commit(self, root: Path, sha: str) -> bool:
        vcpkg = self._has_root_vcpkg()
        conan = self._has_root_conan()

        if not self._has_root_cmake():
            logging.error(f"no CMakeLists.txt at root ({self.repo.full_name})")
            return False
        
        logging.info(f"CMakeLists.txt at root ({self.repo.full_name})")
        analyzer = CMakeAnalyzer(root)
        self.process = CMakeProcess(root, None, [], analyzer, "")

        if not self.process.clone_repo(self.repo_id, root, sha=sha):
            logging.error(f"git cloning failed ({self.repo.full_name})")
            return False
        
        self.process.analyzer.reset()
        if not self.process.analyzer.has_testing(nolist=conf.testing['no_list_testing']):
            logging.error(f"invalid ctest ({self.repo.full_name})")
            return False

        logging.info(f"ctest is defined ({self.repo.full_name})")
        return True
    
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
    
    def _get_cmake_lists(self, dest: Path) -> list[str]:
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