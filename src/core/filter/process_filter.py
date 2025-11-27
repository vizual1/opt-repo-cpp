import tempfile, logging
from src.cmake.process import CMakeProcess
from src.gh.clone import GitHandler
from github.Repository import Repository
from src.cmake.analyzer import CMakeAnalyzer
from src.config.config import Config
from src.core.filter.structure_filter import StructureFilter
from src.core.filter.flags_filter import FlagFilter
from pathlib import Path
from typing import Optional

class ProcessFilter:
    def __init__(self, repo: Repository, config: Config, root: Optional[Path] = None, sha: str = ""):
        self.config = config
        self.repo = repo
        self.root = root
        self.sha = sha if sha else self.repo.get_commits()[0].sha

    def commit_setup_and_build(
        self, 
        msg: str, 
        container_name: str, 
        docker_image: str = ""
    ) -> Optional[StructureFilter]:
        structure = StructureFilter(self.repo, self.config, self.root, self.sha)
        
        logging.info(f"[{self.repo.full_name}] Testing {self.sha}...")
        if self.root and not structure.is_valid_commit(self.root, self.sha, docker_test_dir=self.config.testing.docker_test_dir):
            logging.error(f"[{self.repo.full_name}] commit cmake and ctest failed ({self.sha})")
            return None
        
        process = structure.process
        if not process:
            logging.error(f"[{self.repo.full_name}] CMakeProcess for {self.repo.full_name} couldn't be found")
            return None
        
        analyzer = process.analyzer
        flags = FlagFilter(self.config.valid_test_flags, analyzer.has_build_testing_flag()).get_valid_flags()
        sorted_testing_path = self.sort_testing_path(analyzer.get_enable_testing_path())
        if len(sorted_testing_path) == 0:
            logging.error(f"[{self.repo.full_name}] path to enable_testing() was not found in {self.root}: {sorted_testing_path}")
            return None

        if len(sorted_testing_path) > 1:
            logging.warning(f"[{self.repo.full_name}] multiple paths to enable_testing() was found in {self.root}. For testing: {sorted_testing_path[0]}")

        test_path = sorted_testing_path[0]
        if test_path.name == "CMakeLists.txt":
            test_path = test_path.parent
        enable_testing_path = test_path.relative_to(self.root) if self.root else Path()
        logging.info(f"[{self.repo.full_name}] path to enable_testing(): '{enable_testing_path}'")
        try:
            process.set_enable_testing(enable_testing_path)
            process.set_flags(flags)
            process.docker_image = self.config.docker_image
            if docker_image:
                new = False
            else:
                new = True
            process.start_docker_image(self.config, container_name, new)
            
            if not process.build():
                logging.error(f"[{self.repo.full_name}] {msg} build failed ({self.sha})")
                return None
            
            if not process.collect_tests():
                logging.error(f"[{self.repo.full_name}] {msg} generating test commands failed ({self.sha})")
                return None
            
            logging.info(f"[{self.repo.full_name}] {msg} build successful ({self.sha})")
            return structure
        
        except Exception as e:
            logging.exception(f"[{self.repo.full_name}] Unexpected error during process run: {e}")
            return None
        
    def test_run(self, msg: str, command: list[str], structure: StructureFilter, has_list_args: bool) -> bool:
        if structure.process:
            process = structure.process
            try:
                if not process.test(command, has_list_args):
                    logging.error(f"[{self.repo.full_name}] {msg} test failed ({self.sha})")
                    return False
                
                logging.debug(f"[{self.repo.full_name}] {msg} build and test successful ({self.sha})")
                return True
            except Exception as e:
                logging.exception(f"[{self.repo.full_name}] Unexpected error during process run: {e}")
                return False
        else:
            logging.error(f"[{self.repo.full_name}] CMakeProcess is not defined ({self.sha})")
            return False

    def _sort_key(self, y: Path) -> tuple[int, int]:
        valid_test_dirs = [Path(x) for x in self.config.valid_test_dirs]
        try:
            priority = 0 if any(y.is_relative_to(x) for x in valid_test_dirs) else 1
        except:
            priority = 0
        return (priority, len(y.parts))
    
    def sort_testing_path(self, paths: list[Path]) -> list[Path]: 
        return sorted(paths, key=self._sort_key)
