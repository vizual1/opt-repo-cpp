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
    """
    The Process filters checks if the repository or commit can be build and run.
    """
    def __init__(self, repo: Repository, config: Config, root: Optional[Path] = None, sha: str = ""):
        self.config = config
        self.repo = repo
        self.root = root
        self.sha = sha if sha else self.repo.get_commits()[0].sha

    def valid_run(self, container_name: str) -> bool:
        tmp_root = Path.cwd()/"tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=tmp_root) as tmpdir:
            tmp_path = Path(tmpdir)
            process = CMakeProcess(self.repo.full_name, self.config, tmp_path, None, [], CMakeAnalyzer(tmp_path), "", jobs=self.config.resources.jobs, docker_test_dir=self.config.testing.docker_test_dir)
        
            if not GitHandler().clone_repo(self.repo.full_name, tmp_path):
                logging.error(f"[{self.repo.full_name}:{self.sha}] git cloning failed")
                return False
            
            analyzer = process.analyzer
            analyzer.reset()
            if not analyzer.has_testing(nolist=self.config.testing.no_list_testing):
                logging.error(f"[{self.repo.full_name}:{self.sha}] invalid ctest")
                return False
            
            self.list_test_arg = analyzer.get_list_test_arg()

            flags = FlagFilter(self.config.valid_test_flags, analyzer.extract_build_testing_flag()).get_valid_flags()
            sorted_testing_path = self.sort_testing_path(analyzer.get_enable_testing_path())
            if len(sorted_testing_path) == 0:
                logging.error(f"[{self.repo.full_name}:{self.sha}] path to enable_testing() was not found in {tmpdir}: {sorted_testing_path}")
                return False
            
            test_path = sorted_testing_path[0]
            if test_path.name == "CMakeLists.txt":
                test_path = test_path.parent
            enable_testing_path = test_path.relative_to(tmp_path)
            logging.info(f"[{self.repo.full_name}:{self.sha}] path to enable_testing(): '{enable_testing_path}'")
            try:
                process.set_enable_testing(enable_testing_path)
                process.set_flags(flags)
                process.docker_image = self.config.docker_image
                process.start_docker_image(container_name)
            
                if not process.build():
                    logging.error(f"[{self.repo.full_name}:{self.sha}] build failed")
                    process.docker.stop_container(self.repo.full_name)
                    return False
                    
                if not process.collect_tests():
                    logging.error(f"[{self.repo.full_name}:{self.sha}] test failed")
                    process.docker.stop_container(self.repo.full_name)
                    return False
                
                test_cmd = process.test_commands
                has_list_args = len(test_cmd) > 1
                for cmd in test_cmd:
                    if not process.test(cmd, has_list_args):
                        logging.error(f"[{self.repo.full_name}:{self.sha}] test failed ({self.sha})")
                        process.docker.stop_container(self.repo.full_name)
                        return False
                
            except Exception as e:
                logging.exception(f"[{self.repo.full_name}:{self.sha}] Unexpected error during process run: {e}")
                return False

            finally:
                process.docker.stop_container(self.repo.full_name)
            
            return True

    def commit_setup_and_build(
        self, 
        msg: str, 
        container_name: str, 
        docker_image: str = "",
        cpuset_cpus: str = ""
    ) -> Optional[StructureFilter]:
        structure = StructureFilter(self.repo, self.config, self.root, self.sha)

        if not self.root:
            logging.error(f"[{self.repo.full_name}] git project root: {self.root}")
            return None

        if not GitHandler().clone_repo(self.repo.full_name, self.root, sha=self.sha):
            logging.error(f"[{self.repo.full_name}] git cloning failed")
            return None
        
        logging.info(f"[{self.repo.full_name}:{self.sha}] Testing...")
        if not structure.is_valid_commit(self.root, self.sha, docker_test_dir=self.config.testing.docker_test_dir):
            logging.error(f"[{self.repo.full_name}:{self.sha}] commit cmake and ctest failed")
            return None

        process = structure.process
        if not process:
            logging.error(f"[{self.repo.full_name}:{self.sha}] CMakeProcess couldn't be found")
            return None
        
        analyzer = process.analyzer
        # parses all the possible testing flags defined under src/config/constants.py as VALID_TEST_FLAGS
        flags = FlagFilter(self.config.valid_test_flags, analyzer.extract_build_testing_flag()).get_valid_flags()
        
        # possible multiple enable_testing() defined in CMakeLists.txt
        # here: just take enable_testing() closes to project root
        sorted_testing_path = self.sort_testing_path(analyzer.get_enable_testing_path())
        if len(sorted_testing_path) == 0:
            logging.error(f"[{self.repo.full_name}:{self.sha}] path to enable_testing() was not found in {self.root}: {sorted_testing_path}")
            return None
        
        if len(sorted_testing_path) > 1:
            logging.warning(f"[{self.repo.full_name}:{self.sha}] multiple paths to enable_testing() was found in {self.root}. For testing: {sorted_testing_path[0]}")

        test_path = sorted_testing_path[0]
        if test_path.name == "CMakeLists.txt":
            test_path = test_path.parent
        enable_testing_path = test_path.relative_to(self.root) if self.root else Path()
        logging.info(f"[{self.repo.full_name}:{self.sha}] path to enable_testing(): '{enable_testing_path}'")
        try:
            process.set_enable_testing(enable_testing_path)
            process.set_flags(flags)
            new = not docker_image
            if self.config.testdocker or self.config.testpatch:
                process.set_docker(container_name, new)
                process.docker.start_docker_container(container_name, cpuset_cpus)
                process.container = process.docker.container
            else:
                process.docker_image = self.config.docker_image
                process.start_docker_image(container_name, new, cpuset_cpus)

            if new and self.config.diff and not process.diff():
                logging.error(f"[{self.repo.full_name}:{self.sha}] diff application to old (original) commit failed")
                process.docker.stop_container(self.repo.full_name)
                return None
            
            if not process.build():
                logging.error(f"[{self.repo.full_name}:{self.sha}] {msg} build failed")
                process.docker.stop_container(self.repo.full_name)
                return None
            
            if not process.collect_tests():
                logging.error(f"[{self.repo.full_name}:{self.sha}] {msg} generating test commands failed")
                process.docker.stop_container(self.repo.full_name)
                return None
            
            logging.info(f"[{self.repo.full_name}:{self.sha}] {msg} build successful")
            return structure
        
        except Exception as e:
            logging.exception(f"[{self.repo.full_name}:{self.sha}] Unexpected error during process run: {e}")
            return None
        
    def test_run(self, msg: str, command: list[str], structure: StructureFilter, has_list_args: bool) -> bool:
        if structure.process:
            process = structure.process
            try:
                if not process.test(command, has_list_args):
                    logging.error(f"[{self.repo.full_name}:{self.sha}] {msg} test failed")
                    process.docker.stop_container(self.repo.full_name)
                    return False
                
                logging.debug(f"[{self.repo.full_name}:{self.sha}] {msg} build and test successful")
                return True
            except Exception as e:
                logging.exception(f"[{self.repo.full_name}:{self.sha}] Unexpected error during process run: {e}")
                return False
        else:
            logging.error(f"[{self.repo.full_name}:{self.sha}] CMakeProcess is not defined")
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
