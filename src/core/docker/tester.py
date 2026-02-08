import logging, os, stat, shutil, random, json
from tqdm import tqdm
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
from src.utils.exceptions import TestFailed, UndefinedStructureFilter
from src.utils.image_handling import image_exists, image

class DockerTester:
    def __init__(self, repo: Repository, config: Config):
        self.repo = repo
        self.repo_id = self.repo.full_name
        self.config = config

    def run_commit_pair(
        self,
        new_sha: str,
        old_sha: str,
        new_path: Path,
        old_path: Path,
        cpuset_cpus: str = ""
    ) -> None:
        
        with self._commit_pair_test(
            self.config, new_path, old_path, new_sha, old_sha, cpuset_cpus
        ) as (new_times, old_times, new_struct, old_struct):
            logging.info(f"Times Old: {old_times}, New: {new_times}")
            
            if (not new_struct or not old_struct or 
                not new_struct.process or not old_struct.process):
                return
            
            new_build_cmd = [" ".join(s) for s in new_struct.process.build_commands]
            old_build_cmd = [" ".join(s) for s in old_struct.process.build_commands]
            new_test_cmd = [" ".join(s) for s in new_struct.process.test_commands]
            old_test_cmd = [" ".join(s) for s in old_struct.process.test_commands]

            # --genimages just generates the docker image from an existing json results file
            if self.config.genimages and not self.config.test:
                file_name = "_".join(self.repo_id.split("/") + [new_sha]) + ".json"
                json_file = Path(self.config.input, file_name) 
                
                with open(json_file, 'r', errors='ignore') as f:
                    results = json.load(f)

                results["build_info"]["old_build_script"] = old_build_cmd
                results["build_info"]["new_build_script"] = new_build_cmd
                results["build_info"]["old_test_script"] = old_test_cmd
                results["build_info"]["new_test_script"] = new_test_cmd

                with open(json_file, 'w', errors='ignore') as f:
                    json.dump(results, f, indent=4)

                old_struct.process.save_docker_image(self.repo_id, new_sha, new_build_cmd, old_build_cmd, new_test_cmd, old_test_cmd, results)
                logging.info(f"[{self.repo_id}:{new_sha}] Docker image saved.")
                return

            warmup = self.config.testing.warmup

            new_single_tests_d = new_struct.process.per_test_times 
            old_single_tests_d = old_struct.process.per_test_times

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

            commit = self.repo.get_commit(new_sha)
            results = test.create_test_log(
                commit, self.repo, old_sha, new_sha,
                old_times, new_times, new_build_cmd, old_build_cmd, new_test_cmd, old_test_cmd,
            )
            logging.info(f"Results: {results['performance_analysis']}")
            writer = Writer(self.repo_id, self.config.storage_paths["performance"])
            writer.write_results(results)

            old_struct.process.save_docker_image(self.repo_id, new_sha, new_build_cmd, old_build_cmd, new_test_cmd, old_test_cmd, results)
                
            if total_improvement < self.config.min_p_value or overall_change_with_new_outperforms_old:
                logging.info(f"[{self.repo_id}:{new_sha}] significantly improves execution time.")
                writer.write_improve(results)
                        

    @contextmanager
    def _commit_pair_test(
        self, 
        config: Config, 
        new_path: Path, 
        old_path: Path, 
        new_sha: str, 
        old_sha: str,
        cpuset_cpus: str = ""
    ) -> Generator[tuple[list[float], list[float], Optional[StructureFilter], Optional[StructureFilter]], Any, Any]:
        """
        Start a container for new/old commits and stop container automatically after both runs.
        """
        new_pf = ProcessFilter(self.repo, config, new_path, new_sha)
        old_pf = ProcessFilter(self.repo, config, old_path, old_sha)
        docker_image = ""

        new_structure = None
        old_structure = None
        new_times = []
        old_times = []

        try:
            local_image = image(self.repo_id, new_sha)
            container_name = local_image
            if (self.config.testdocker or self.config.testpatch) and not image_exists(self.repo_id, new_sha) and self.config.check_dockerhub:
                container_name = f"{self.config.dockerhub_user}/{self.config.dockerhub_repo}:{local_image}"

            new_structure = new_pf.commit_setup_and_build("New", container_name=container_name, cpuset_cpus=cpuset_cpus)
            docker_image = new_structure.process.docker_image if new_structure and new_structure.process else ""
            
            if not new_structure or not new_structure.process:
                raise UndefinedStructureFilter("New commit StructureFilter or its CMakeProcess is None")

            old_structure = old_pf.commit_setup_and_build("Old", container_name=container_name, docker_image=docker_image)
            
            if not old_structure or not old_structure.process:
                raise UndefinedStructureFilter("Old commit StructureFilter or its CMakeProcess is None")
            
            # --genimages just generates the docker image from an existing json results file
            if (not self.config.genimages or self.config.test):
                self._run_tests(new_structure, old_structure, new_pf, old_pf)

            new_cmd_times = new_structure.process.test_time
            old_cmd_times = old_structure.process.test_time

            new_times = new_cmd_times['time'] if 0.0 in new_cmd_times['parsed'] else new_cmd_times['parsed']
            old_times = old_cmd_times['time'] if 0.0 in old_cmd_times['parsed'] else old_cmd_times['parsed']

            yield new_times, old_times, new_structure, old_structure

        except TestFailed as e:
            logging.error("Test failed early, stopping the test loops.")
            logging.error(str(e))
            yield [], [], None, None

        except UndefinedStructureFilter as e:
            logging.error(str(e))
            yield [], [], None, None

        finally:
            self._remove_cloned_repo_folders(self.repo_id, new_path, old_path)
            if new_structure and new_structure.process:
                new_structure.process.docker.stop_container(self.repo_id)
            elif old_structure and old_structure.process:
                old_structure.process.docker.stop_container(self.repo_id)

    def _run_tests(self, new_structure: StructureFilter, old_structure: StructureFilter, new_pf: ProcessFilter, old_pf: ProcessFilter) -> None:
        if not new_structure.process:
            raise UndefinedStructureFilter("The CMakeProcess in the new commit StructureFilter is None")
        
        if not old_structure.process:
            raise UndefinedStructureFilter("The CMakeProcess in the old commit StructureFilter is None")
            
        new_test_cmd = new_structure.process.test_commands
        old_test_cmd = old_structure.process.test_commands
        logging.debug(f"New cmd: {new_structure.process.test_commands}")
        logging.debug(f"Old cmd: {old_structure.process.test_commands}")
        assert len(new_test_cmd) == len(old_test_cmd)

        warmup = self.config.testing.warmup
        test_repeat = self.config.testing.commit_test_times
        has_list_args = len(new_test_cmd) > 1
        
        try:
            for new_cmd, old_cmd in tqdm(zip(new_test_cmd, old_test_cmd), total=len(new_test_cmd), position=1, leave=False, mininterval=5): 
                for _ in tqdm(range(warmup+test_repeat), total=warmup+test_repeat, desc="Commit pair test", position=2, leave=False, mininterval=5):
                    order = [
                        ("New", new_cmd, new_structure, new_pf),
                        ("Old", old_cmd, old_structure, old_pf),
                    ]
                    random.shuffle(order)

                    for label, cmd, structure, pf in order:
                        if cmd and cmd[0] == "cd":
                            continue
                        if not pf.test_run(label, cmd, structure, has_list_args):
                            raise TestFailed(f"Test run '{cmd}' failed")
        except TestFailed:
            has_list_args = False
            new_test_cmd = old_test_cmd = [["ctest", "--output-on-failure"]]
            for new_cmd, old_cmd in tqdm(zip(new_test_cmd, old_test_cmd), total=len(new_test_cmd), position=1, leave=False, mininterval=5): 
                for _ in tqdm(range(warmup+test_repeat), total=warmup+test_repeat, desc="Commit pair test", position=2, leave=False, mininterval=5):
                    order = [
                        ("New", new_cmd, new_structure, new_pf),
                        ("Old", old_cmd, old_structure, old_pf),
                    ]
                    random.shuffle(order)

                    for label, cmd, structure, pf in order:
                        if not pf.test_run(label, cmd, structure, has_list_args):
                            raise TestFailed(f"Test run '{cmd}' with test framework '{label}' failed")
            

    def _remove_cloned_repo_folders(self, repo_id: str, new_path: Path, old_path: Path):
        try:
            if new_path.exists():
                shutil.rmtree(new_path, onerror=self._on_rm_error)
            if old_path.exists():
                shutil.rmtree(old_path, onerror=self._on_rm_error)
            if old_path.parent.exists():
                shutil.rmtree(old_path.parent, onerror=self._on_rm_error)
        except PermissionError as e:
            logging.warning(f"[{repo_id}] Failed to delete {new_path} or {old_path}")

    def _on_rm_error(self, func, path, exc_info):
        os.chmod(path, stat.S_IWRITE)
        func(path)
