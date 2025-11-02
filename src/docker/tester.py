import logging, subprocess, os, stat
from src.cmake.process import DockerManager
from src.cmake.analyzer import CMakeAnalyzer
from src.filter.structure_filter import StructureFilter
from src.filter.process_filter import ProcessFilter
from src.utils.config import Config
from src.utils.stats import is_exec_time_improvement_significant
from pathlib import Path
from src.utils.parser import parse_ctest_output
from src.utils.writer import Writer
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Any
import shutil

class DockerTester:
    def __init__(self, config: Config):
        self.config = config
        self.analyzer = CMakeAnalyzer(Path())

    def run_commit_pair(
        self,
        repo: str,
        new_sha: str,
        old_sha: str,
        new_path: Path,
        old_path: Path,
    ) -> None:
        try:
            with self._commit_pair_test(
                repo, self.config, new_path, old_path, new_sha, old_sha
            ) as (new_times, old_times, new_struct, old_struct):
                logging.info(f"Times Old: {old_times}, New: {new_times}")
                warmup = self.config.testing["warmup"]

                if is_exec_time_improvement_significant(
                    self.config.commits_dict['min-exec-time-improvement'], 
                    self.config.commits_dict['min-p-value'], 
                    new_times[warmup:], old_times[warmup:]
                ):
                    if new_struct and new_struct.process and old_struct and old_struct.process:
                        new_cmd = new_struct.process.commands
                        old_cmd = old_struct.process.commands
                        old_struct.process.save_docker_image(repo, new_sha, new_cmd, old_cmd)

                    logging.info(f"[{repo}] ({new_sha}) significantly improves execution time.")
                    Writer(repo, self.config.output or self.config.storage["performance"]).write_improve(new_sha, old_sha)

        except Exception as e:
            logging.exception(f"[{repo}] Error running commit pair test: {e}")

        finally:
            for struct in [new_struct, old_struct]:
                try:
                    if struct and struct.process:
                        struct.process.docker.stop_container()
                        break
                except Exception as e:
                    logging.warning(f"[{repo}] Failed to stop container: {e}")

    @contextmanager
    def _commit_pair_test(
        self, 
        repo: str, 
        config: Config, 
        new_path: Path, 
        old_path: Path, 
        new_sha: str, 
        old_sha: str
    ) -> Generator[tuple[list[float], list[float], Optional[StructureFilter], Optional[StructureFilter]], Any, Any]:
        """
        Start a container for new/old commits and stop container automatically after both runs.
        """
        new_pf = ProcessFilter(repo, config, new_path, new_sha)
        old_pf = ProcessFilter(repo, config, old_path, old_sha)
        docker_image = ""

        new_structure = None
        old_structure = None
        new_times = []
        old_times = []
        
        try:
            new_times, new_structure = new_pf.valid_commit_run("New", container_name=new_sha)
            docker_image = new_structure.process.docker_image if new_structure and new_structure.process else ""
            
            old_times, old_structure = old_pf.valid_commit_run("Old", container_name=new_sha, docker_image=docker_image)

            yield new_times, old_times, new_structure, old_structure
            
        finally:
            try:
                if new_path.exists():
                    shutil.rmtree(new_path, onerror=self._on_rm_error)
                if old_path.exists():
                    shutil.rmtree(old_path, onerror=self._on_rm_error)
            except PermissionError as e:
                logging.warning(f"[{repo}] Failed to delete {new_path} or {old_path}")

            for struct in [new_structure, old_structure]:
                try:
                    if struct and struct.process:
                        struct.process.docker.stop_container()
                        break
                except Exception as e:
                    logging.warning(f"[{repo}] Failed to stop container: {e}")
                
    def _on_rm_error(self, func, path, exc_info):
        os.chmod(path, stat.S_IWRITE)
        func(path)


    def test_input_folder(self) -> None:
        """Test all Docker images in input folder"""
        input_path = Path(self.config.input)
        if not input_path.exists():
            raise ValueError(f"Input folder {self.config.input} does not exist")
        
        for tar_file in input_path.glob("*.tar"):
            image_name = tar_file.stem
            logging.info(f"Testing image: {image_name}")
            significant = self._test_docker_image(image_name, tar_file)
            if significant:
                logging.info(f"[{image_name}] improves the performance significantly.")
            else:
                logging.info(f"[{image_name}] does not improve the performance.")

    def _test_docker_image(self, image_name: str, tar_file: Path) -> bool:
        cmd = ["docker", "load", "-i", str(tar_file)]
        subprocess.run(cmd)

        try:
            docker = DockerManager(Path(), image_name, self.config.testing['docker_test_dir'])
            docker.start_docker_container(image_name)

            new_times: list[float] = []
            old_times: list[float] = []
            warmup: int = self.config.testing['warmup']
            for _ in range(warmup + self.config.testing['commit_test_times']):
                cmd = ["bash", f"{self.config.testing['docker_test_dir']}/new_test.sh"]
                exit_code, stdout, stderr = docker.run_command_in_docker(cmd, Path())
                stats = parse_ctest_output(stdout)
                elapsed: float = stats['total_time_sec']
                new_times.append(elapsed)

                cmd = ["bash", f"{self.config.testing['docker_test_dir']}/old_test.sh"]
                exit_code, stdout, stderr = docker.run_command_in_docker(cmd, Path())
                stats = parse_ctest_output(stdout)
                elapsed: float = stats['total_time_sec']
                old_times.append(elapsed)

            return is_exec_time_improvement_significant(
                self.config.commits_dict['min-exec-time-improvement'],
                self.config.commits_dict['min-p-value'],
                new_times[warmup:], old_times[warmup:])
        
        except:
            logging.error("")
            return False

        finally:
            docker.stop_container()


    def test_mounted_against_docker(self, docker_image: str, mount: str):
        """Test mounted directory against saved Docker image"""
        mount_dir = Path(mount)
        
        if not mount_dir.exists():
            raise ValueError(f"Mount directory {mount_dir} does not exist")
        
        # TODO: .tar file or docker image, check if docker_image already exist
        if docker_image.endswith(".tar"):
            cmd = ["docker", "load", "-i", str(docker_image)]
            subprocess.run(cmd)
            docker_image = docker_image.removesuffix(".tar")
        docker = DockerManager(mount_dir, docker_image, self.config.testing['docker_test_dir'])
        docker.start_docker_container(docker_image)
