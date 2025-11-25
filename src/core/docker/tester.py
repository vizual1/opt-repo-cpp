import logging, subprocess, os, stat, shutil
from src.core.docker.manager import DockerManager
from src.cmake.analyzer import CMakeAnalyzer
from src.core.filter.structure_filter import StructureFilter
from src.core.filter.process_filter import ProcessFilter
from src.config.config import Config
from src.utils.test_analyzer import TestAnalyzer
from pathlib import Path
from src.utils.parser import *
from src.utils.writer import Writer
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Any
from github.Repository import Repository

class DockerTester:
    def __init__(self, config: Config):
        self.config = config
        self.analyzer = CMakeAnalyzer(Path())

    def run_commit_pair(
        self,
        repo: Repository,
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
                
                if new_struct and new_struct.process and old_struct and old_struct.process:
                    warmup = self.config.testing.warmup

                    new_single_tests = new_struct.process.per_test_times
                    old_single_tests = old_struct.process.per_test_times

                    test = TestAnalyzer(
                        self.config, new_single_tests, old_single_tests
                    )

                    total_improvement = test.get_improvement_p_value(
                        old_times[warmup:], new_times[warmup:] 
                    )
                    logging.info(f"pvalue: {total_improvement}")

                    isolated_improvements = test.get_significant_test_time_changes()
                    logging.info(f"new outperforms old: {isolated_improvements['new_outperforms_old']}")
                    overall_change = test.get_overall_change()
                    logging.info(f"overall change: {overall_change}")
                    overall_change_with_new_outperforms_old = (
                        len(isolated_improvements['new_outperforms_old']) > 0 and 
                        overall_change > self.config.overall_decline_limit
                    )

                    new_cmd = new_struct.process.commands
                    old_cmd = old_struct.process.commands
                    
                    commit = repo.get_commit(new_sha)
                    results = test.create_test_log(
                        commit, repo, old_sha, new_sha, 
                        old_times, new_times, old_cmd, new_cmd
                    )
                    logging.info(f"Results: {results['performance_analysis']}")
                    writer = Writer(repo.full_name, self.config.output_file or self.config.storage_paths["performance"])
                    writer.write_results(results)

                    if total_improvement < self.config.commits_time['min-p-value'] or overall_change_with_new_outperforms_old:
                        old_struct.process.save_docker_image(repo.full_name, new_sha, new_cmd, old_cmd, results)
                        logging.info(f"[{repo.full_name}] ({new_sha}) significantly improves execution time.")
                        writer.write_improve(results)
                        

        except Exception as e:
            logging.exception(f"[{repo.full_name}] Error running commit pair test: {e}")

        finally:
            for struct in [new_struct, old_struct]:
                try:
                    if struct and struct.process:
                        struct.process.docker.stop_container()
                except Exception as e:
                    logging.warning(f"[{repo.full_name}] Failed to stop container: {e}")

    @contextmanager
    def _commit_pair_test(
        self, 
        repo: Repository, 
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
        except Exception:
            for struct in [new_structure, old_structure]:
                try:
                    if struct and struct.process:
                        struct.process.docker.stop_container()
                except Exception as e:
                    logging.warning(f"[{repo.full_name}] Failed to stop container: {e}")
            
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
                except Exception as e:
                    logging.warning(f"[{repo.full_name}] Failed to stop container: {e}")
                
    def _on_rm_error(self, func, path, exc_info):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    def test_input_folder(self) -> None:
        """Test all Docker images in input folder"""
        input_path = Path(self.config.input_file)
        if not input_path.exists():
            raise ValueError(f"Input folder {self.config.input_file} does not exist")
        
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
            docker = DockerManager(self.config, Path(), image_name, self.config.testing.docker_test_dir)
            docker.start_docker_container(image_name)

            new_times: list[float] = []
            old_times: list[float] = []
            warmup: int = self.config.testing.warmup
            for _ in range(warmup + self.config.testing.commit_test_times):
                cmd = ["bash", f"{self.config.testing.docker_test_dir}/new_test.sh"]
                exit_code, stdout, stderr, time = docker.run_command_in_docker(cmd, Path())
                stats = parse_ctest_output(stdout)
                elapsed: float = stats['total_time_sec']
                new_times.append(elapsed)

                cmd = ["bash", f"{self.config.testing.docker_test_dir}/old_test.sh"]
                exit_code, stdout, stderr, time = docker.run_command_in_docker(cmd, Path())
                stats = parse_ctest_output(stdout)
                elapsed: float = stats['total_time_sec']
                old_times.append(elapsed)
                
            #test = TestAnalyzer(self.config, [], [], warmup, self.config.testing.commit_test_times)
            return True #test.get_improvement_p_value(new_times[warmup:], old_times[warmup:]) < self.config.commits_time['min-p-value']
        
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
        docker = DockerManager(self.config, mount_dir, docker_image, self.config.testing.docker_test_dir)
        docker.start_docker_container(docker_image)

    