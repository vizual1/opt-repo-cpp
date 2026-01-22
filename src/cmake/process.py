import logging, subprocess, tempfile, json
from pathlib import Path
from src.cmake.analyzer import CMakeAnalyzer
from src.cmake.resolver import DependencyResolver
from src.utils.parser import *
from typing import Optional, Union
from src.core.docker.manager import DockerManager
from src.config.config import Config
from src.utils.permission import check_and_fix_path_permissions
from src.utils.image_handling import image

class CMakeProcess:
    """Class configures, builds, tests, and clones commits."""
    def __init__(
        self, 
        repo_id: str,
        config: Config,
        root: Path, 
        enable_testing_path: Optional[Path], 
        flags: list[str], 
        analyzer: CMakeAnalyzer, 
        package_manager: str,
        jobs: int = 1,
        docker_test_dir: str = ""
    ):
        self.config = config
        self.repo_id = repo_id
        self.project_root = Path(__file__).resolve().parents[2]
        self.root = (self.project_root / root).resolve() if not root.is_absolute() else root.resolve()
        self.docker_test_dir = docker_test_dir.replace("\\", "/")
        self.build_path = Path(self.to_container_path(self.root / "build"))
        self.test_path = self.build_path / (enable_testing_path if enable_testing_path else "")
        
        self.flags: list[str] = flags
        self.analyzer = analyzer
        self.package_manager = package_manager
        self.jobs = jobs

        self.container = None
        self.docker_image: str = ""
        self.config_stdout: str = ""
        self.config_stderr: str = ""
        self.build_stdout: str = ""
        self.build_stderr: str = ""
        self.test_flags: set[str] = set()
        self.other_flags: dict[str, list[str]] = {"append": [], "remove": []}
        self.other_cmds: list[list[str]] = []
        self.resolver = DependencyResolver(self.config)
        self.test_time: dict[str, list[float]] = {
            "parsed": [0.0 for _ in range(self.config.testing.warmup + self.config.testing.commit_test_times)], 
            "time": [0.0 for _ in range(self.config.testing.warmup + self.config.testing.commit_test_times)]
        }
        self.test_commands: list[list[str]] = []
        self.build_commands: list[list[str]] = []
        self.cmake_config_output: list[str] = []
        self.cmake_build_output: list[str] = []
        self.ctest_output: list[str] = []
        self.per_test_times: dict[str, dict[str, list[float]]] = {}
        self.framework: str = ""
        self.unit_tests_map: dict[str, dict[str, str]] = {}

    def set_enable_testing(self, enable_testing_path: Path) -> None:
        self.root = self.root
        self.test_path = Path(self.build_path, enable_testing_path)

    def set_flags(self, flags: list[str]) -> None:
        self.flags = flags

    def set_docker(self, docker_image: str, new: bool):
        self.docker = DockerManager(self.config, self.root.parent, docker_image, self.docker_test_dir, new)

    def start_docker_image(self, container_name: str, new: bool = True, cpuset_cpus: str = "") -> None:
        if not self.docker_image:
            self.docker_image = self.analyzer.get_docker()
        logging.info(f"Started Docker Image: {self.docker_image}")
        self.set_docker(self.docker_image, new)
        self.docker.start_docker_container(container_name, cpuset_cpus)
        self.container = self.docker.container

        copy_cmd = ["cp", "-r", "/workspace", self.docker_test_dir]
        exit_code, stdout, stderr, _ = self.docker.run_command_in_docker(copy_cmd, self.root, check=False)
        if exit_code != 0:
            logging.error(f"Copy files failed with exit code {exit_code}: {' '.join(map(str, copy_cmd))}")
            if stdout: logging.info(f"stdout: {stdout}")
            if stderr: logging.warning(f"stderr: {stderr}")
        else:
            logging.info(f"Files copied into docker: {' '.join(map(str, copy_cmd))}")
            if stdout: logging.info(f"stdout: {stdout}")


    def save_docker_image(
            self, repo_id: str, sha: str, 
            new_build_cmd: list[str], old_build_cmd: list[str], 
            new_test_cmd: list[str], old_test_cmd: list[str],
            results_json: dict) -> None:
        """
        Saved docker image structure:
        | /workspace -- mount folder
        | /test_workspace 
            | /workspace
                | /old -- old commit => OK
                | /new -- new commit => OK
            | /logs => OK
                | full.log -- full log of configure, build and test output
                | config.log -- log of configure run
                | build.log -- log of build run
                | test.log -- log of test run
                | results.json -- tested results, statistics, metadata and other informations
            | old_build.sh -- old configure and build code used => OK
            | new_build.sh -- new configure and build code used => OK
            | old_test.sh -- old ctest used => OK
            | new_test.sh -- new ctest used => OK
        """
        image_name = image(repo_id, sha)
        container_id = self.container.id if self.container and self.container.id else "test"
        
        inspect = subprocess.run(
            ["docker", "image", "inspect", image_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if inspect.returncode == 0:
            logging.info(f"Removing existing image: {image_name}")
            rm = subprocess.run(
                ["docker", "rmi", "-f", image_name],
                capture_output=True,
                text=True
            )
            if rm.returncode != 0:
                logging.error(f"Failed to remove old image {image_name}: {rm.stderr}")

        self.copy_log_to_container(container_id, results_json)
        self.docker.copy_commands_to_container(self.root, new_build_cmd, old_build_cmd, new_test_cmd, old_test_cmd)

        clean_cmd = [
            ["apt-get", "autoremove", "-y"], 
            ["apt-get", "autoclean", "-y"], 
            ["apt-get", "clean"], 
            ["rm", "-rf", "/var/lib/apt/lists/*"], 
            ["rm", "-rf", "/tmp/*"], 
            ["rm", "-rf", "/root/.cache"], 
            ["rm", "-rf", "/home/*/.cache"]
        ]
        for cmd in clean_cmd:
            exit_code, stdout, stderr, _ = self.docker.run_command_in_docker(cmd, self.root, check=False)
            if exit_code != 0:
                logging.error(f"Failed command exit code {exit_code}: {' '.join(map(str, cmd))}")
                if stdout: logging.info(f"stdout: {stdout}")
                if stderr: logging.warning(f"stderr: {stderr}")
            
        result = subprocess.run(["docker", "commit", container_id, image_name], capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"docker commit failed: {result.stderr}")
        
        if self.config.tar:
            result = subprocess.run(["docker", "save", image_name, "-o", f"{image_name}.tar"], capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"docker save failed: {result.stderr}")

    def copy_log_to_container(self, container_id: str, results_json: dict) -> None:
        log_config: str = f"Configuration output:\n" + '\n'.join(self.cmake_config_output) + "\n"
        log_build: str = f"Build output:\n" + '\n'.join(self.cmake_build_output) + "\n"
        log_test: str = f"Test output:\n" + '\n'.join(self.ctest_output) + "\n"
        log_full: str = log_config + log_build + log_test
        results: dict = results_json
        
        logs: list[Union[str, dict]] = [log_full, log_config, log_build, log_test, results]
        name: list[str] = ["full", "config", "build", "test", "results"]

        for log, n in zip(logs, name):
            data_type = ".log" if n != "results" else ".json"
            with tempfile.NamedTemporaryFile("w", delete=False, suffix=data_type) as tmp_file:
                if isinstance(log, str):
                    tmp_file.write(log)
                else:
                    json.dump(results, tmp_file, indent=4)
                tmp_path = Path(tmp_file.name)

                dest_path = f"{container_id}:{self.docker_test_dir}/logs/{n}{data_type}"
                check_and_fix_path_permissions(self.root)
                result = subprocess.run(["docker", "cp", str(tmp_path), dest_path],
                                        capture_output=True, text=True)

                if result.returncode != 0:
                    logging.error(f"Copying log file failed: {result.stderr}")
                else:
                    logging.info(f"Copied log file to {dest_path}")

############### RUNNING ###############
        
    def configure(self) -> bool:
        return self._configure()

    def build(self) -> bool:
        return self._configure_with_retries() #and self._build()
    
    def test(self, cmd: list[str], has_list_args: bool) -> bool:
        return self._ctest(cmd, has_list_args)

    def collect_tests(self) -> bool:
        return self._ctest_collection()
    
############### CONFIGURATION ###############
    
    def _configure_with_retries(self, max_retries: int = 10) -> bool:
        save_dependencies = set()
        save_resolutions: dict[str, list[str]] = {"append": [], "remove": [], "command": []}
        save_commands: list[str] = []
        unresolved_dependencies: set[str] = set() 

        if not self.container:
            logging.error(f"No docker container started")
            return False

        parsed = False
        for attempt in range(max_retries):
            logging.info(f"[Attempt {attempt+1}/{max_retries}] Configuring project at {self.root}")

            #remove_build = ["rm", "-rf", str(self.build_path).replace("\\", "/")]
            #self.docker.run_command_in_docker(remove_build, self.root, check=False)
            
            if self._configure():
                self.build_commands.reverse() # 1. build, 2. configure -> reversed
                self.build_commands = self.resolver.install_cmds + self.build_commands
                return True
            
            missing_dependencies = self.resolver.package_handler.get_missing_dependencies(
                self.config_stdout, 
                self.config_stderr, 
                self.build_stdout,
                self.build_stderr,
                Path(self.build_path) / "CMakeCache.txt"
            )

            missing_dependencies -= save_dependencies
            
            self.other_flags, self.other_cmds = self.resolver.flag.find_resolve(
                self.config_stdout, 
                self.config_stderr, 
                self.build_stdout,
                self.build_stderr,
                self.other_flags,
                self.other_cmds
            )

            has_other_resolutions = (self.other_flags["append"] or self.other_flags["remove"] or self.other_cmds)
            if not missing_dependencies and not has_other_resolutions and not parsed:
                missing_dependencies = self.analyzer.get_dependencies()
                unresolv, oflags = self.resolver.resolve_all(missing_dependencies, self.container)
                unresolved_dependencies |= unresolv
                self.test_flags |= oflags
                parsed = True
            elif not missing_dependencies and not has_other_resolutions:
                logging.error("Configuration failed but no missing dependencies detected")
                break
            
            append_flags_in_save = set(self.other_flags["append"]) <= set(save_resolutions["append"])
            remove_flags_in_save = set(self.other_flags["remove"]) <= set(save_resolutions["remove"])
            new_commands_in_save = set([" ".join(c) for c in self.other_cmds]) <= set(save_commands)
            if not missing_dependencies and append_flags_in_save and remove_flags_in_save and new_commands_in_save and not parsed:
                missing_dependencies = self.analyzer.get_dependencies()
                unresolv, oflags = self.resolver.resolve_all(missing_dependencies, self.container)
                unresolved_dependencies |= unresolv
                self.test_flags |= oflags
                parsed = True
            elif not missing_dependencies and append_flags_in_save and remove_flags_in_save and new_commands_in_save:
                logging.error("Configuration failed but no new missing dependencies detected")
                break
            
            for cmd in self.other_cmds:
                self.docker.run_command_in_docker(cmd, self.root, check=False)

            unresolv, oflags = self.resolver.resolve_all(missing_dependencies, self.container)
            unresolved_dependencies |= unresolv
            self.test_flags |= oflags
            
            if unresolved_dependencies:
                unresolved_dependencies, oflags = self.resolver.unresolved_dep(unresolved_dependencies)
                self.test_flags |= oflags

            save_resolutions = self.other_flags
            save_commands = [" ".join(c) for c in self.other_cmds]
            save_dependencies |= missing_dependencies

        logging.error("All configuration attempts failed.")
        return False
    

    def _configure(self, commands: list[str] = []) -> bool:
        cmd = [
            #'cmake', 
            #'-E', 'env', 
            #'PKG_CONFIG_PATH=/opt/vcpkg/installed/x64-linux/lib/pkgconfig',
            #'CMAKE_PREFIX_PATH=/opt/vcpkg/installed/x64-linux',
            #'LD_LIBRARY_PATH=/opt/vcpkg/installed/x64-linux/lib',

            'cmake',
            '-S', self.to_container_path(self.root), 
            '-B', str(self.build_path).replace("\\", "/"), 
            #'-G', 'Ninja',

            #'-DVCPKG_MANIFEST_MODE=ON',
            #'-DVCPKG_MANIFEST_DIR=' + self.root,  # vcpkg.json location
            #'-DVCPKG_INSTALLED_DIR=' + str(Path(self.build_path) / 'vcpkg_installed'),  # isolate deps per build
            
            '-DCMAKE_BUILD_TYPE=Debug',
            #'-DCMAKE_BUILD_TYPE=RelWithDebInfo',
            #'-DCMAKE_C_COMPILER=/usr/bin/clang',
            #'-DCMAKE_CXX_COMPILER=/usr/bin/clang++',
            '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',

            # disable errors for warnings
            #'-DCMAKE_CXX_FLAGS=-g -Wall -Wextra -Wpedantic -Wno-error',
            #'-DCMAKE_C_FLAGS=-g -Wall -Wextra -Wpedantic -Wno-error',
            #'-DCMAKE_CXX_FLAGS_DEBUG=-g -Wall -Wextra -Wpedantic -Wno-error',
            #'-DCMAKE_C_FLAGS_DEBUG=-g -Wall -Wextra -Wpedantic -Wno-error',

            #'-DCMAKE_C_FLAGS=-fprofile-instr-generate -fcoverage-mapping -O0 -g',
            #'-DCMAKE_CXX_FLAGS=-fprofile-instr-generate -fcoverage-mapping -O0 -g',
            #'-DCMAKE_EXE_LINKER_FLAGS=-fprofile-instr-generate',
            #'-DCMAKE_C_COMPILER_LAUNCHER=ccache',
            #'-DCMAKE_CXX_COMPILER_LAUNCHER=ccache',

            #'-DCMAKE_VERBOSE_MAKEFILE=ON',
            #'-DCMAKE_FIND_DEBUG_MODE=ON',
        ]

        for flag in self.flags:
            if 'disable' in flag.lower():
                cmd.append(f'-D{flag}=OFF')
            else:
                cmd.append(f'-D{flag}=ON')

        for flag in self.other_flags["append"]:
            cmd.append(flag)
        
        for flag in self.other_flags["remove"]:
            if flag in cmd:
                cmd.remove(flag)
    
        if self.package_manager.startswith("vcpkg"):
            logging.info("Installing through package manager vcpkg...")
            cmd.append('-DCMAKE_TOOLCHAIN_FILE=/opt/vcpkg/scripts/buildsystems/vcpkg.cmake')
            cmd.append('-DVCPKG_MANIFEST_MODE=ON')
        """
        elif self.package_manager.startswith("conanfile"):
            try:
                logging.info("Installing through package manager conan...")
                install = ['conan', 'install', '.', '-build=missing'] 
                exit_code, stdout, stderr, _ = self.docker.run_command_in_docker(install, self.root, workdir=self.root, check=False)
                self.cmake_config_output.append(stdout)
                if exit_code == 0:
                    logging.info(f"Conan Output:\n{stdout}")
                else:
                    if stdout: logging.error(f"Conan Output (stdout):\n{stdout}")
                    if stderr: logging.error(f"Conan Error (stderr):\n{stderr}")
                    return False
            except Exception as e:
                logging.error(f"Conan installation failed: {e}")
                return False
        """

        logging.info(" ".join(map(str, cmd)))
        exit_code, stdout, stderr, _ = self.docker.run_command_in_docker(cmd, self.root, check=False)

        if exit_code == 0:
            logging.info(f"CMake Configuration successful for {self.build_path}")
            logging.debug(f"Output:\n{stdout}")
        else:
            logging.error(f"CMake configuration failed for {self.build_path} (return code {exit_code})", exc_info=True)
            self.config_stdout = stdout
            self.config_stderr = stderr
            if stdout: logging.error(f"Output (stdout):\n{stdout}")
            if stderr: logging.error(f"Error (stderr):\n{stderr}")
            #remove_build = ["rm", "-rf", str(self.build_path).replace("\\", "/")]
            #self.docker.run_command_in_docker(remove_build, self.root, check=False)
            #if not commands:
            #    for flag in self.test_flags:
            #        cmd.append(flag)
            #    return self._configure(cmd)
            return False
        
        if not self._build():
            return False
        
        self.build_commands.append(list(map(str, cmd)))
        return True
        
    def to_container_path(self, path: Path) -> str:
        rel = path.relative_to(self.root.parent)
        return f"{self.docker_test_dir}/workspace/{rel.as_posix()}"
    
############### BUILDING ###############

    def _build(self) -> bool:
        cmd = ['cmake', '--build', str(self.build_path).replace("\\", "/"), '--']
        if self.jobs > 0:
            cmd += ['-j', str(self.jobs)]

        logging.info(" ".join(map(str, cmd)))

        exit_code, stdout, stderr, _ = self.docker.run_command_in_docker(cmd, self.root, check=False)
        self.cmake_build_output.append(stdout)
        if exit_code == 0:
            logging.info(f"CMake build completed for {self.root}")
            logging.debug(f"Output:\n{stdout}")
            self.build_commands.append(list(map(str, cmd)))
            return True
        else:
            logging.error(f"CMake build failed for {self.root} (return code {exit_code})", exc_info=True)
            self.build_stdout = stdout
            self.build_stderr = stderr
            if stdout: logging.error(f"Output (stdout):\n{stdout}", exc_info=True)
            if stderr: logging.error(f"Error (stderr):\n{stderr}", exc_info=True)
            return False
        
    def check_build(self) -> bool:
        cmd = ["test", "-d", str(self.build_path).replace("\\", "/")]
        exit_code, stdout, stderr, _ = self.docker.run_command_in_docker(cmd, self.root, check=False)
        if exit_code == 0:
            logging.info(f"Build is already completed {self.root}")
            logging.debug(f"Output:\n{stdout}")
            return True
        else:
            logging.warning(f"No build found in {self.root} (return code {exit_code})", exc_info=True)
            if stdout: logging.warning(f"Output (stdout):\n{stdout}", exc_info=True)
            if stderr: logging.warning(f"Error (stderr):\n{stderr}", exc_info=True)
            return False

############### TEST COLLECTION ###############

    def _ctest_collection(self) -> bool:
        cmd = self._check_tests_exists()
        if not cmd:
            return False
        
        test_exec_flag = self.analyzer.get_list_test_arg()
        if test_exec_flag and not self._individual_tests_collection(test_exec_flag):
            return False

        logging.info(f"Commands: {self.test_commands}")
        if len(self.test_commands) == 0: # no test commands
            root = ['cd', str(self.test_path)]
            self.test_commands.append(list(map(str, root))) # TODO: test
            self.test_commands.append(list(map(str, cmd)))
        return True

    def _individual_tests_collection(self, test_exec_flag: list[tuple[str, str]]) -> bool:
        framework, test_flag = test_exec_flag[0]

        path = str(self.docker_test_dir / self.test_path / 'CTestTestfile.cmake').replace("\\", "/")
        cmd = ["cat", f"{path}"]
        exit_code, stdout, stderr, time = self.docker.run_command_in_docker(
            cmd, self.root, workdir=self.docker_test_dir/self.test_path, check=False
        )

        logging.debug(f"CTestTestfile.cmake output:\n{stdout}")
        test_exec: set[str] = set(self.analyzer.parse_ctest_file(stdout))

        # collect path from subdirs(path) in CTestTestfile.cmake files
        subdirs = self.analyzer.parse_subdirs(stdout)
        for subdir in subdirs:
            path = str(self.docker_test_dir / self.test_path / subdir / 'CTestTestfile.cmake').replace("\\", "/")
            cmd = ["cat", f"{path}"]
            exit_code, stdout, stderr, time = self.docker.run_command_in_docker(
                cmd, self.root, workdir=self.docker_test_dir/self.test_path, check=False
            )
            logging.debug(f"CTestTestfile.cmake output:\n{stdout}")
            test_exec |= set(self.analyzer.parse_ctest_file(stdout))

        if not test_exec:
            logging.info("No test executables found.")

        # collect all the unit tests on the exe_path
        unit_tests: dict[str, list[str]] = {}
        for exe_path in test_exec:
            cmd = [exe_path, test_flag]
            logging.debug(' '.join(map(str, cmd)))
            exit_code, stdout, stderr, time = self.docker.run_command_in_docker(
                cmd, self.root, workdir=self.docker_test_dir/self.test_path, check=False
            )
            tests = self.analyzer.extract_unit_tests(stdout, framework)
            logging.info(f"{test_flag} ({framework}) output:\n{stdout}")
            if tests:
                unit_tests[exe_path] = tests

        logging.debug(f"unit tests: {unit_tests}")

        if not unit_tests:
            logging.info("No unit tests found.")

        # single test run via specific framework and exe_path
        for exe_path, test_names in unit_tests.items():
            for test_name in test_names:
                self.per_test_times[test_name] = {"parsed": [], "time": []}
                command = self._single_test_collection(exe_path, framework, test_name)
                self.test_commands.append(command)
                self.unit_tests_map[" ".join(command)] = {"name": test_name, "exe": exe_path}

        logging.debug(f"Unit test map: {self.unit_tests_map}")
        self.framework = framework
        return True


    def _single_test_collection(self, exe_path: str, framework: str, test_name: str) -> list[str]:
        if framework == "gtest":
            cmd = [f"{exe_path}", f"--gtest_filter={test_name}", "--gtest_print_time"]
        elif framework == "catch":
            cmd = [f"{exe_path}", f"\"{test_name}\"", "--durations", "yes"]
        elif framework == "doctest":
            cmd = [f"{exe_path}", f"--test-case={test_name}"]
        elif framework == "boost":
            cmd = [f"{exe_path}", f"--run_test={test_name}", "--log_level=test_suite", "--report_level=detailed"]
        elif framework == "qt":
            cmd = [f"{exe_path}", f"\"{test_name}\""]
        else:
            raise ValueError(f"Unknown framework for {exe_path}")
        
        return list(map(str, cmd))
    

    def _check_tests_exists(self) -> list[str]:
        cmd = ['ctest', '--output-on-failure', '--fail-if-no-tests']
        try:
            # check if any tests exist
            exit_code, stdout, stderr, _ = self.docker.run_command_in_docker(
                ['ctest', '--help'], self.root, workdir=self.test_path, check=False
            )
            if '--fail-if-no-tests' not in stdout:
                # fallback for older cmake versions
                check_cmd = ['ctest', '-N']
                exit_code, stdout_check, _, _ = self.docker.run_command_in_docker(
                    check_cmd, self.root, workdir=self.test_path, check=False
                )
                if 'No tests were found' in stdout_check or 'Test #' not in stdout_check:
                    logging.error(f"No tests found in {self.test_path}")
                    return []
                
                cmd = ['ctest', '--output-on-failure']
            
            return cmd
        
        except Exception as e:
            logging.error(f"CTest checking failed: {e}", exc_info=True)
            return cmd
        

############### TESTING ###############

    def _ctest(self, command: list[str], has_list_args: bool) -> bool:
        if has_list_args and self._individual_ctest(command):
            return True
        
        if 0.0 not in self.test_time['parsed'] or 0.0 not in self.test_time['time']:
            # too many tests
            return True
        
        try:
            logging.info(f"{' '.join(command)} in {self.test_path}")
            exit_code, stdout, stderr, time = self.docker.run_command_in_docker(
                command, self.root, workdir=self.docker_test_dir/self.test_path, check=False, timeout=self.config.max_test_time, log=False,
            )

            # parse the times returned
            stats = parse_ctest_output(stdout)
            elapsed: float = stats['total_time_sec']

            idx = self.test_time['parsed'].index(0.0)
            self.test_time['parsed'][idx] = elapsed
            idx = self.test_time['time'].index(0.0)
            self.test_time['time'][idx] = time

            self.ctest_output.append(stdout)
            self.per_test_times = parse_single_ctest_output(stdout, self.per_test_times)

            if exit_code == 0 or (elapsed != 0.0 and stats['passed'] > 0):
                logging.info(f"CTest passed for {self.test_path}")
                logging.debug(f"Output:\n{stdout}")
                logging.info(f"Tests run: {stats['total']}, Failures: {stats['failed']}, Skipped: {stats['skipped']}, Time elapsed: {elapsed or time} s")
            else:
                logging.error(f"CTest failed for {self.test_path} (return code {exit_code}) with command {' '.join(command)}", exc_info=True)
                if stdout: logging.error(f"Output (stdout):\n{stdout}", exc_info=True)
                if stderr: logging.error(f"Error (stderr):\n{stderr}", exc_info=True)
                return False
            
            # TODO: run this tests, each with different profile
            #cmd = ['LLVM_PROFILE_FILE=coverage/%t.profraw', exec, test_name]
            # extract the profraw coverage without the test and build folders
            # extract coverage data and create
            return True
            
        except Exception as e:
            logging.error(f"CTest execution failed: {e}", exc_info=True)
            return False
        

    def _individual_ctest(self, command: list[str], extra: list[str] = []) -> bool:
        unit_map = self.unit_tests_map[" ".join(command)]
        test_name = unit_map['name']
        exe_path = unit_map['exe']

        if (len(self.per_test_times[test_name]['parsed']) >= len(self.test_time['parsed']) and
            len(self.per_test_times[test_name]['time']) >= len(self.test_time['time'])):
            # probably duplicate test_name
            return True

        logging.debug(command + extra)
        exit_code, stdout, stderr, time = self.docker.run_command_in_docker(
            command + extra, self.root, check=False, timeout=self.config.max_test_time, log=False
        )
        logging.debug(f"Individual CTest stdout:\n{stdout}")

        elapsed: float = parse_framework_output(stdout, self.framework, test_name)
                    
        if elapsed < 0.0:
            return False
        
        if elapsed == 0.0:
            test_exec_flag = self.analyzer.get_list_test_arg()
            framework, _ = test_exec_flag[0]
            if framework == "gtest" and not extra:
                return self._individual_ctest(command, ["--gtest_repeat=100"])
            elapsed = parse_usr_bin_time(stdout)

        ntest = len(self.per_test_times[test_name]['parsed'])
        self.per_test_times[test_name]['parsed'].append(elapsed)
        self.per_test_times[test_name]['time'].append(time)
        self.test_time['parsed'][ntest] += elapsed
        self.test_time['time'][ntest] += time

        if exit_code == 0:
            logging.debug(f"CTest passed for {self.test_path}")
            logging.debug(f"Output:\n{stdout}")
            logging.debug(f"[{test_name}] Time elapsed: {elapsed or time} s")
        else:
            logging.error(f"CTest failed for {self.test_path} (return code {exit_code}) with command {' '.join(command)}", exc_info=True)
            logging.error(f"Output (stdout):\n{stdout[:10000]}", exc_info=True)
            logging.error(f"Error (stderr):\n{stderr[:10000]}", exc_info=True)
            return False

        self.ctest_output.append(stdout)
        return True