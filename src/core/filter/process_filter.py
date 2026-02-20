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
    def __init__(self, config: Config, root: Optional[Path] = None):
        self.config = config
        self.root = root

    def valid_run(self, container_name: str, repo: Repository, sha: str = "") -> bool:
        sha = sha if sha else repo.get_commits()[0].sha 
        tmp_root = Path.cwd()/"tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=tmp_root) as tmpdir:
            tmp_path = Path(tmpdir)
            process = CMakeProcess(self.config, tmp_path, None, [], CMakeAnalyzer(tmp_path), "")
        
            if not GitHandler().clone_repo(repo.full_name, tmp_path):
                logging.error(f"[{repo.full_name}:{sha}] git cloning failed")
                return False
            
            analyzer = process.analyzer
            analyzer.reset()
            if not analyzer.has_testing(nolist=self.config.testing.no_list_testing):
                logging.error(f"[{repo.full_name}:{sha}] invalid ctest")
                return False
            
            self.list_test_arg = analyzer.get_list_test_arg()

            flags = FlagFilter(self.config.valid_test_flags, analyzer.extract_build_testing_flag()).get_valid_flags()
            sorted_testing_path = self.sort_testing_path(analyzer.get_enable_testing_path())
            if len(sorted_testing_path) == 0:
                logging.error(f"[{repo.full_name}:{sha}] path to enable_testing() was not found in {tmpdir}: {sorted_testing_path}")
                return False
            
            test_path = sorted_testing_path[0]
            if test_path.name == "CMakeLists.txt":
                test_path = test_path.parent
            enable_testing_path = test_path.relative_to(tmp_path)
            logging.info(f"[{repo.full_name}:{sha}] path to enable_testing(): '{enable_testing_path}'")
            try:
                process.set_enable_testing(enable_testing_path)
                process.set_flags(flags)
                process.docker_image = self.config.docker_image
                process.start_docker_image(container_name)
            
                if not process.build():
                    logging.error(f"[{repo.full_name}:{sha}] build failed")
                    process.docker.stop_container(repo.full_name)
                    return False
                    
                if not process.collect_tests():
                    logging.error(f"[{repo.full_name}:{sha}] test failed")
                    process.docker.stop_container(repo.full_name)
                    return False
                
                test_cmd = process.test_commands
                has_list_args = len(test_cmd) > 1
                for cmd in test_cmd:
                    if not process.test(cmd, has_list_args):
                        logging.error(f"[{repo.full_name}:{sha}] test failed")
                        process.docker.stop_container(repo.full_name)
                        return False
                
            except Exception as e:
                logging.exception(f"[{repo.full_name}:{sha}] Unexpected error during process run: {e}")
                return False

            finally:
                process.docker.stop_container(repo.full_name)
            
            return True

    def commit_setup_and_build(
        self, 
        msg: str,
        repo: Repository,
        sha: str,
        container_name: str, 
        startup: bool = True,
        cpuset_cpus: str = "",
    ) -> Optional[CMakeProcess]:
        
        if not self.root:
            logging.error(f"[{repo.full_name}] git project root: {self.root}")
            return None

        if not GitHandler().clone_repo(repo.full_name, self.root, sha=sha):
            logging.error(f"[{repo.full_name}] git cloning failed")
            return None
        
        structure = StructureFilter(self.config, self.root)
        logging.info(f"[{repo.full_name}:{sha}] Testing...")
        if not structure.is_valid_commit(repo, self.root, sha):
            logging.error(f"[{repo.full_name}:{sha}] commit cmake and ctest failed")
            return None

        analyzer = structure.analyzer
        process = CMakeProcess(self.config, self.root, None, [], analyzer, "")
        if not process:
            logging.error(f"[{repo.full_name}:{sha}] CMakeProcess couldn't be found")
            return None
        
        # parses all the possible testing flags defined under src/config/constants.py in VALID_TEST_FLAGS
        flags = FlagFilter(self.config.valid_test_flags, analyzer.extract_build_testing_flag()).get_valid_flags()
        
        # possible multiple enable_testing() defined in CMakeLists.txt
        # here: just take enable_testing() closes to project root
        sorted_testing_path = self.sort_testing_path(analyzer.get_enable_testing_path())
        if len(sorted_testing_path) == 0:
            logging.error(f"[{repo.full_name}:{sha}] path to enable_testing() was not found in {self.root}: {sorted_testing_path}")
            return None
        
        if len(sorted_testing_path) > 1:
            logging.warning(f"[{repo.full_name}:{sha}] multiple paths to enable_testing() was found in {self.root}. For testing: {sorted_testing_path[0]}")

        test_path = sorted_testing_path[0]
        if test_path.name == "CMakeLists.txt":
            test_path = test_path.parent
        enable_testing_path = test_path.relative_to(self.root) if self.root else Path()
        logging.info(f"[{repo.full_name}:{sha}] path to enable_testing(): '{enable_testing_path}'")
        try:
            return self.build_collect_test(repo, sha, process, enable_testing_path, flags, container_name, startup, cpuset_cpus, msg)
        except Exception as e:
            logging.exception(f"[{repo.full_name}:{sha}] Unexpected error during process run: {e}")
            return None
        
    def docker_commit_setup_and_build(
        self, 
        msg: str, 
        container_name: str, 
        startup: bool = True,
        cpuset_cpus: str = ""
    ) -> Optional[CMakeProcess]:
        if not self.root:
            logging.error(f"[{self.config.docker_image}] git project root: {self.root}")
            return None
        
        analyzer = CMakeAnalyzer(self.root)
        process = CMakeProcess(self.config, self.root, None, [], analyzer, "")
        
        process.docker_image = self.config.docker_image
        process.set_docker(container_name, startup)
        process.docker.start_docker_container(container_name, cpuset_cpus)
        process.container = process.docker.container
        if not process.get_commands_in_docker(startup):
            logging.error(f"[{self.config.docker_image}] {msg} copying commands from the docker image failed")
            return None
        
        if startup and self.config.diff and not process.diff():
            logging.error(f"[{self.config.docker_image}] diff application to old (original) commit failed")
            process.docker.stop_container(self.config.docker_image)
            return None
        
        if self.config.diff and not process.build_in_docker():
            logging.error(f"[{self.config.docker_image}] {msg} commit building failed")
            process.docker.stop_container(self.config.docker_image)
            return None

        logging.info(f"[{self.config.docker_image}] {msg} docker commit setup successful.")
        return process

        
    def build_collect_test(
        self, 
        repo: Repository, 
        sha: str,
        process: CMakeProcess, 
        enable_testing_path: Path, 
        flags: list[str],
        container_name: str,
        startup: bool,
        cpuset_cpus: str,
        msg: str
    ) -> Optional[CMakeProcess]:
        
        process.set_enable_testing(enable_testing_path)
        process.set_flags(flags)

        #if self.config.testdocker or self.config.testpatch:
        #    process.docker_image = self.config.docker_image
        #    process.set_docker(container_name, startup)
        #    process.docker.start_docker_container(container_name, cpuset_cpus)
        #    process.container = process.docker.container
        #else: # self.config.testdocker and not self.config.testpatch: 

        process.docker_image = self.config.docker_image
        process.start_docker_image(container_name, startup, cpuset_cpus)

        #if startup and self.config.diff and not process.diff():
        #    logging.error(f"[{repo.full_name}:{sha}] diff application to old (original) commit failed")
        #    process.docker.stop_container(repo.full_name)
        #    return None
        
        if not process.build():
            logging.error(f"[{repo.full_name}:{sha}] {msg} build failed")
            process.docker.stop_container(repo.full_name)
            return None
        
        if not process.collect_tests():
            logging.error(f"[{repo.full_name}:{sha}] {msg} generating test commands failed")
            process.docker.stop_container(repo.full_name)
            return None
        
        logging.info(f"[{repo.full_name}:{sha}] {msg} build successful")
        return process

    def _sort_key(self, y: Path) -> tuple[int, int]:
        valid_test_dirs = [Path(x) for x in self.config.valid_test_dirs]
        try:
            priority = 0 if any(y.is_relative_to(x) for x in valid_test_dirs) else 1
        except:
            priority = 0
        return (priority, len(y.parts))
    
    def sort_testing_path(self, paths: list[Path]) -> list[Path]: 
        return sorted(paths, key=self._sort_key)
