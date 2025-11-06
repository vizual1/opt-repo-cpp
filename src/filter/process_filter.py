import tempfile, logging
from src.cmake.process import CMakeProcess
from src.gh.clone import GitHandler
from src.cmake.analyzer import CMakeAnalyzer
from src.utils.config import Config
from src.filter.structure_filter import StructureFilter
from src.filter.flags_filter import FlagFilter
from pathlib import Path
from typing import Optional

class ProcessFilter:
    def __init__(self, repo_id: str, config: Config, root: Optional[Path] = None, sha: str = ""):
        self.repo_id = repo_id
        self.config = config
        self.repo = self.config.git.get_repo(self.repo_id)
        self.root = root
        self.sha = sha if sha else self.repo.get_commits()[0].sha

    def valid_run(self, container_name: str, docker_test_dir: str) -> bool:
        tmp_root = Path.cwd()/"tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=tmp_root) as tmpdir:
            tmp_path = Path(tmpdir)
            analyzer = CMakeAnalyzer(tmp_path)
            process = CMakeProcess(tmp_path, None, [], analyzer, "", docker_test_dir=docker_test_dir)

            if not GitHandler().clone_repo(self.repo_id, tmp_path):
                logging.error(f"[{self.repo_id}] git cloning failed")
                return False
            
            process.analyzer.reset()
            if not process.analyzer.has_testing(nolist=self.config.testing['no_list_testing']):
                logging.error(f"[{self.repo_id}] invalid ctest")
                return False
            
            self.list_test_arg = list(process.analyzer.parser.list_test_arg)

            flags = FlagFilter(process.analyzer.has_build_testing_flag()).get_valid_flags()
            sorted_testing_path = self.sort_testing_path(process.analyzer.parser.enable_testing_path)
            if len(sorted_testing_path) == 0:
                logging.error(f"[{self.repo_id}] path to enable_testing() was not found in {tmpdir}: {sorted_testing_path}")
                return False
            
            test_path = sorted_testing_path[0]
            if test_path.name == "CMakeLists.txt":
                test_path = test_path.parent
            enable_testing_path = test_path.relative_to(tmp_path)
            logging.info(f"[{self.repo_id}] path to enable_testing(): '{enable_testing_path}'")
            try:
                process.set_enable_testing(enable_testing_path)
                process.set_flags(flags)
                process.docker_image = self.config.docker
                process.start_docker_image(container_name)
            
                if not process.build():
                    logging.error(f"[{self.repo_id}] build failed")
                    return False
                    
                if not process.test([], test_repeat=1):
                    logging.error(f"[{self.repo_id}] test failed")
                    return False
                
            except Exception as e:
                logging.exception(f"[{self.repo_id}] Unexpected error during process run: {e}")
                return False

            finally:
                try:
                    process.docker.stop_container()
                except Exception as e:
                    logging.warning(f"[{self.repo_id}] Failed to stop container: {e}")
            
            return True
        
    def valid_commit_run(
        self, 
        msg: str, 
        container_name: str, 
        docker_image: str = ""
    ) -> tuple[list[float], Optional[StructureFilter]]:
        structure = StructureFilter(self.repo_id, self.config, self.root, self.sha)

        logging.info(f"[{self.repo_id}] Testing {self.sha}...")
        if self.root and not structure.is_valid_commit(self.root, self.sha, docker_test_dir=self.config.testing['docker_test_dir']):
            logging.error(f"[{self.repo_id}] commit cmake and ctest failed ({self.sha})")
            return [], None
        
        if not structure.process:
            logging.error(f"[{self.repo_id}] CMakeProcess for {self.repo_id} couldn't be found")
            return [], None
        
        flags = FlagFilter(structure.process.analyzer.has_build_testing_flag()).get_valid_flags()
        sorted_testing_path = self.sort_testing_path(structure.process.analyzer.parser.enable_testing_path)
        if len(sorted_testing_path) == 0:
            logging.error(f"[{self.repo_id}] path to enable_testing() was not found in {self.root}: {sorted_testing_path}")
            return [], None
        
        test_path = sorted_testing_path[0]
        if test_path.name == "CMakeLists.txt":
            test_path = test_path.parent
        enable_testing_path = test_path.relative_to(self.root) if self.root else Path()
        logging.info(f"[{self.repo_id}] path to enable_testing(): '{enable_testing_path}'")
        try:
            structure.process.set_enable_testing(enable_testing_path)
            structure.process.set_flags(flags)
            structure.process.docker_image = self.config.docker
            if docker_image:
                structure.process.set_docker(self.config.docker or docker_image, new=False)
            structure.process.start_docker_image(container_name)
            
            if not structure.process.build():
                logging.error(f"[{self.repo_id}] {msg} build failed ({self.sha})")
                return [], None
                
            if not structure.process.test([], warmup=self.config.testing['warmup'] , test_repeat=self.config.testing['commit_test_times']):
                logging.error(f"[{self.repo_id}] {msg} test failed ({self.sha})")
                return [], None
            
            commands = structure.process.commands
            test_time = structure.process.test_time
            logging.info(f"[{self.repo_id}] {msg} build and test successful ({self.sha})")
            return test_time, structure
        
        except Exception as e:
            logging.exception(f"[{self.repo_id}] Unexpected error during process run: {e}")
            return [], None

    def _sort_key(self, y: Path) -> tuple[int, int]:
        valid_test_dirs = [Path(x) for x in self.config.valid_test_dir]
        try:
            priority = 0 if any(y.is_relative_to(x) for x in valid_test_dirs) else 1
        except:
            priority = 0
        return (priority, len(y.parts))
    
    def sort_testing_path(self, paths: list[Path]) -> list[Path]: 
        return sorted(paths, key=self._sort_key)
