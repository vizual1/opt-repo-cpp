import logging, os, stat, shutil, random, json
from tqdm import tqdm
from src.core.filter.process_filter import ProcessFilter
from src.cmake.process import CMakeProcess
from src.config.config import Config
from src.utils.test_analyzer import TestAnalyzer
from pathlib import Path
from src.utils.parser import *
from src.utils.writer import Writer
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional, Any
from github.Repository import Repository
from src.utils.exceptions import TestFailed, UndefinedStructureFilter
from src.utils.image_handling import image_exists, image

class DockerTester:
    def __init__(self, config: Config):
        #self.repo = repo
        #self.repo_id = self.repo.full_name
        self.config = config

    def run_commit_pair(
        self,
        repo: Repository,
        new_sha: str,
        old_sha: str,
        new_path: Path,
        old_path: Path,
        cpuset_cpus: str = "",
    ) -> None:
        with self._commit_pair_test(
            repo, new_path, old_path, new_sha, old_sha, cpuset_cpus
        ) as (new_process, old_process):
            
            if not new_process or not old_process:
                return

            if self.config.genimages and not self.config.test:
                self._gen_image_only(repo, new_process, old_process, new_sha)
            else:
                self._analyzer_results(repo, new_process, old_process, new_sha, old_sha)
                        

    @contextmanager
    def _commit_pair_test(
        self, 
        repo: Repository,
        new_path: Path, 
        old_path: Path, 
        new_sha: str, 
        old_sha: str,
        cpuset_cpus: str = ""
    ) -> Generator[tuple[Optional[CMakeProcess], Optional[CMakeProcess]], Any, Any]:
        """
        Start a container for new/old commits and stop container automatically after both runs.
        """
        try:
            new_process, old_process = self._setup_commits(repo, new_path, old_path, new_sha, old_sha, cpuset_cpus)
            # --genimages just generates the docker image from an existing json results file
            if (not self.config.genimages or self.config.test):
                self._run_tests(repo, new_process, old_process, new_sha)
            
            yield new_process, old_process

        except TestFailed as e:
            logging.error("Test failed early, stopping the test loops.")
            logging.error(str(e))
            yield None, None

        except UndefinedStructureFilter as e:
            logging.error(str(e))
            yield None, None

        finally:
            msg = repo.full_name if repo else self.config.docker_image
            self._remove_commits_folders(msg, new_path, old_path)
            if new_process:
                new_process.docker.stop_container(msg)
            elif old_process:
                old_process.docker.stop_container(msg)


    def _setup_commits(
        self, 
        repo: Repository,
        new_path: Path, 
        old_path: Path, 
        new_sha: str, 
        old_sha: str,
        cpuset_cpus: str = "",
    ) -> tuple[CMakeProcess, CMakeProcess]:
        new_pf = ProcessFilter(self.config, new_path)
        old_pf = ProcessFilter(self.config, old_path)
        docker_image = ""

        new_process = None
        old_process = None

        if self.config.docker_image and image_exists(other=self.config.docker_image):
            container_name = self.config.docker_image

            new_process = new_pf.docker_commit_setup_and_build("New", container_name=container_name, startup=True, cpuset_cpus=cpuset_cpus)
            
            if not new_process:
                raise UndefinedStructureFilter("New commit CMakeProcess is None")
            
            old_process = old_pf.docker_commit_setup_and_build("Old", container_name=container_name, startup=False)

            if not old_process:
                raise UndefinedStructureFilter("Old commit CMakeProcess is None")
            
            return new_process, old_process
        
        else: 
            local_image = image(repo.full_name, new_sha)
            container_name = local_image

            new_process = new_pf.commit_setup_and_build("New", repo, new_sha, container_name=container_name, startup=True, cpuset_cpus=cpuset_cpus)
            
            if not new_process:
                raise UndefinedStructureFilter("New commit CMakeProcess is None")

            old_process = old_pf.commit_setup_and_build("Old", repo, old_sha, container_name=container_name, startup=False)
            
            if not old_process:
                raise UndefinedStructureFilter("Old commit CMakeProcess is None")
            
            return new_process, old_process


    def _run_tests(self, repo: Repository, new_process: CMakeProcess, old_process: CMakeProcess, new_sha: str) -> None:
        if not new_process:
            raise UndefinedStructureFilter("The CMakeProcess for the new commit is None")
        
        if not old_process:
            raise UndefinedStructureFilter("The CMakeProcess for the old commit is None")
            
        new_test_cmd = new_process.test_commands
        old_test_cmd = old_process.test_commands
        logging.debug(f"New cmd: {new_process.test_commands}")
        logging.debug(f"Old cmd: {old_process.test_commands}")
        assert len(new_test_cmd) == len(old_test_cmd)
        has_test_framework = bool(new_process.framework)

        self._test(repo, new_process, old_process, has_test_framework, new_test_cmd, old_test_cmd, new_sha)

    def _test(self, repo: Repository, new_process: CMakeProcess, old_process: CMakeProcess, has_test_framework: bool, new_test_cmd: list[list[str]], old_test_cmd: list[list[str]], new_sha: str) -> None: 
        warmup = self.config.testing.warmup
        test_repeat = self.config.testing.commit_test_times
        msg = f"{repo.full_name}:{new_sha}" if repo else self.config.docker_image

        for new_cmd, old_cmd in tqdm(zip(new_test_cmd, old_test_cmd), total=len(new_test_cmd), position=1, leave=False, mininterval=5): 
            for _ in tqdm(range(warmup+test_repeat), total=warmup+test_repeat, desc="Commit pair test", position=2, leave=False, mininterval=5):
                order = [
                    ("New", new_cmd, new_process),
                    ("Old", old_cmd, old_process),
                ]
                random.shuffle(order)

                for label, cmd, process in order:
                    if cmd and cmd[0] == "cd":
                        continue
                    if not process.test(cmd, has_test_framework):
                        logging.error(f"[{msg}] {label} test failed")
                        #process.docker.stop_container(repo.full_name if repo else self.config.docker_image)
                        raise TestFailed(f"Test run '{cmd}' failed")
                    logging.debug(f"[{msg}] {label} build and test successful")
    
    
    def _analyzer_results(self, repo: Repository, new_process: CMakeProcess, old_process: CMakeProcess, new_sha: str, old_sha: str) -> None:
        new_cmd_times = new_process.test_time
        old_cmd_times = old_process.test_time

        new_times = new_cmd_times['time'] if 0.0 in new_cmd_times['parsed'] else new_cmd_times['parsed']
        old_times = old_cmd_times['time'] if 0.0 in old_cmd_times['parsed'] else old_cmd_times['parsed']

        logging.info(f"Times Old: {old_times}, New: {new_times}")

        new_build_cmd = [" ".join(s) for s in new_process.build_commands]
        old_build_cmd = [" ".join(s) for s in old_process.build_commands]
        new_test_cmd = [" ".join(s) for s in new_process.test_commands]
        old_test_cmd = [" ".join(s) for s in old_process.test_commands]

        warmup = self.config.testing.warmup

        new_single_tests_d = new_process.per_test_times 
        old_single_tests_d = old_process.per_test_times

        new_single_tests = {
            test: (
                new_single_tests_d[test]['parsed']
                if 0.0 not in new_single_tests_d[test]['parsed']
                else new_single_tests_d[test]['time']
            )
            for test in new_single_tests_d.keys()
        }

        old_single_tests = {
            test: (
                old_single_tests_d[test]['parsed']
                if 0.0 not in old_single_tests_d[test]['parsed']
                else old_single_tests_d[test]['time']
            )
            for test in old_single_tests_d.keys()
        }
        
        test = TestAnalyzer(
            self.config, new_single_tests, old_single_tests
        )

        total_improvement = test.get_pair_improvement_p_value(
            old_times[warmup:], new_times[warmup:] 
        )
        logging.info(f"pvalue: {total_improvement}")

        isolated_improvements = test.get_significant_test_time_changes(test.get_pair_improvement_p_value)
        logging.info(f"new outperforms old: {isolated_improvements['new_outperforms_old']}")
        overall_change = test.get_overall_change()
        logging.info(f"overall change: {overall_change}")
        overall_change_with_new_outperforms_old = (
            len(isolated_improvements['new_outperforms_old']) > 0 and 
            overall_change > self.config.overall_decline_limit and
            len(isolated_improvements['old_outperforms_new']) == 0
        )

        commit = repo.get_commit(new_sha)
        results = test.create_test_log(
            commit, repo, old_sha, new_sha,
            old_times, new_times, new_build_cmd, old_build_cmd, new_test_cmd, old_test_cmd,
        )
        logging.info(f"Results: {results['performance_analysis']}")
        writer = Writer(repo.full_name, self.config.output or self.config.storage_paths["performance"])
        writer.write_results(results)

        old_process.save_docker_image(repo.full_name, new_sha, new_build_cmd, old_build_cmd, new_test_cmd, old_test_cmd, results)
            
        if total_improvement < self.config.min_p_value or overall_change_with_new_outperforms_old:
            logging.info(f"[{repo.full_name}:{new_sha}] significantly improves execution time.")
            writer.write_improve(results)

    def _gen_image_only(self, repo: Repository, new_process: CMakeProcess, old_process: CMakeProcess, new_sha: str):
        '''Generates the docker image from an existing json results file'''
        new_build_cmd = [" ".join(s) for s in new_process.build_commands]
        old_build_cmd = [" ".join(s) for s in old_process.build_commands]
        new_test_cmd = [" ".join(s) for s in new_process.test_commands]
        old_test_cmd = [" ".join(s) for s in old_process.test_commands]

        file_name = "_".join(repo.full_name.split("/") + [new_sha]) + ".json"
        json_file = Path(self.config.input, file_name) 
        
        with open(json_file, 'r', errors='ignore') as f:
            results = json.load(f)

        results["build_info"]["old_build_script"] = old_build_cmd
        results["build_info"]["new_build_script"] = new_build_cmd
        results["build_info"]["old_test_script"] = old_test_cmd
        results["build_info"]["new_test_script"] = new_test_cmd

        with open(json_file, 'w', errors='ignore') as f:
            json.dump(results, f, indent=4)

        old_process.save_docker_image(repo.full_name, new_sha, new_build_cmd, old_build_cmd, new_test_cmd, old_test_cmd, results)
        logging.info(f"[{repo.full_name}:{new_sha}] Docker image saved.")

    def _remove_commits_folders(self, msg: str, new_path: Path, old_path: Path) -> None:
        try:
            if new_path.exists():
                shutil.rmtree(new_path, onerror=self._on_rm_error)
            if old_path.exists():
                shutil.rmtree(old_path, onerror=self._on_rm_error)
            if old_path.parent.exists():
                shutil.rmtree(old_path.parent, onerror=self._on_rm_error)
        except PermissionError as e:
            logging.warning(f"[{msg}] Failed to delete {new_path} or {old_path}")

    def _on_rm_error(self, func, path, exc_info):
        os.chmod(path, stat.S_IWRITE)
        func(path)
