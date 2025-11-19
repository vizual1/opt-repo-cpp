import logging, tempfile, os
from collections import Counter
from github.GitTreeElement import GitTreeElement
from github.Repository import Repository
from typing import Optional
from pathlib import Path
from github.ContentFile import ContentFile

from src.config.config import Config
from src.cmake.analyzer import CMakeAnalyzer
from src.cmake.process import CMakeProcess
from src.gh.clone import GitHandler
from src.utils.stats import RepoStats

class StructureFilter:
    """
    This class analyses and filters the structure of a repository.
    """
    def __init__(self, repo: Repository, config: Config, root: Optional[Path] = None, sha: str = ""):
        self.config = config
        self.repo = repo
        self.root = root
        self.sha = sha if sha else self.repo.get_commits()[0].sha

        self.cmake_tree, self.tree_paths, self.tree = self._get_repo_tree()
        self.root_files = {item.path for item in self.tree if item.type == "blob"}
        self.stats = RepoStats()
        self.testing_flags: dict = {}
        self.process: Optional[CMakeProcess] = None

    def is_valid(self, without_pkg_manager: bool = True) -> bool:
        vcpkg = self._has_root_vcpkg()
        conan = self._has_root_conan()

        if not self._has_root_cmake() or not (without_pkg_manager or vcpkg or conan):
            logging.warning(f"[{self.repo.full_name}] no CMakeLists.txt at root found")
            return False
        
        logging.info(f"[{self.repo.full_name}] CMakeLists.txt at root found")

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmpdir:
            tmpdir = Path(tmpdir)
            self._get_cmake_lists(tmpdir)
            analyzer = CMakeAnalyzer(tmpdir)

            analyzer.reset()
            if not analyzer.has_testing(nolist=self.config.testing.no_list_testing):
                logging.warning(f"[{self.repo.full_name}] invalid ctest")
                return False
            
            test_dirs = self._extract_test_dirs()
            if test_dirs:
                logging.debug(f"[{self.repo.full_name}] test directories: {test_dirs}")
                for d in test_dirs:
                    self.stats.test_dirs[d] += 1
                conv_test_dir = test_dirs & self.config.valid_test_dirs

                if conv_test_dir:
                    logging.debug(f"[{self.repo.full_name}] conventional test directories {conv_test_dir}")
                    self.testing_flags = analyzer.has_build_testing_flag()
                    self.test_flags = Counter(self.testing_flags.keys())
            
            logging.info(f"[{self.repo.full_name}] ctest is defined")
            return True
                
    def is_valid_commit(self, root: Path, sha: str, docker_test_dir: str) -> bool:
        vcpkg = self._has_root_vcpkg()
        conan = self._has_root_conan()

        if not self._has_root_cmake():
            logging.error(f"[{self.repo.full_name}] no CMakeLists.txt at root found")
            return False
        
        logging.info(f"[{self.repo.full_name}] CMakeLists.txt at root found")
        analyzer = CMakeAnalyzer(root)
        self.process = CMakeProcess(self.config, root, None, [], analyzer, "", jobs=self.config.resources.jobs, docker_test_dir=docker_test_dir)

        if not GitHandler().clone_repo(self.repo.full_name, root, sha=sha):
            logging.error(f"[{self.repo.full_name}] git cloning failed")
            return False
        
        self.process.analyzer.reset()
        if not self.process.analyzer.has_testing(nolist=self.config.testing.no_list_testing):
            logging.error(f"[{self.repo.full_name}] invalid ctest")
            return False

        logging.info(f"[{self.repo.full_name}] ctest is defined")
        return True
    
    def _has_root_cmake(self) -> bool:
        return self._has_root_file("CMakeLists.txt")
    
    def _has_root_vcpkg(self) -> bool:
        return self._has_root_file("vcpkg.json")
    
    def _has_root_conan(self) -> bool:
        return self._has_root_file("conanfile.txt") or self._has_root_file("conanfile.py")
    
    def _has_root_bazel(self) -> bool:
        return self._has_root_file("WORKSPACE") or self._has_root_file("MODULE.bazel")

    def _has_root_meson(self) -> bool:
        return self._has_root_file("meson.build")
    
    def _has_root_file(self, filename: str) -> bool:
        return filename in self.root_files

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
        result_paths = []
        for item in self.cmake_tree:
            try: 
                content_file = self.repo.get_contents(item.path, ref=self.sha)
                target_path = dest / item.path
                os.makedirs(target_path.parent, exist_ok=True)
                if isinstance(content_file, ContentFile):
                    with open(target_path, "wb") as f:
                        f.write(content_file.decoded_content)
                    result_paths.append(str(target_path))
            except Exception as e:
                logging.warning(f"[{self.repo.full_name}] Failed to fetch/write {item.path}: {e}")

        return result_paths

    def _extract_test_dirs(self) -> set[str]:
        """Extracts all directories that look like test directories from a PyGithub GitTree."""
        test_dirs: set[str] = set()

        for element in self.tree: 
            path = element.path.lower()
            parts = path.split("/")

            for i, part in enumerate(parts[:-1]):
                if any(keyword in part for keyword in self.config.test_keywords):
                    test_dir = "/".join(parts[:i+1])
                    test_dirs.add(test_dir)

        top_level_dirs: set[str] = set()
        for dir_path in test_dirs:
            if not any(dir_path != other and dir_path.startswith(other + "/") for other in test_dirs):
                top_level_dirs.add(dir_path)

        return top_level_dirs