
import logging, subprocess, os, shutil, docker
from pathlib import Path
from src.cmake.analyzer import CMakeAnalyzer
from src.cmake.resolver import DependencyResolver
from docker.types import Mount
from typing import Optional
import posixpath

vcpkg_pc = "/opt/vcpkg/installed/x64-linux/lib/pkgconfig"
os.environ["PKG_CONFIG_PATH"] = f"{vcpkg_pc}:{os.environ.get('PKG_CONFIG_PATH','')}"

class CMakeProcess:
    """Class configures, builds, tests, and clones commits."""
    def __init__(
        self, 
        root: Path, 
        enable_testing_path: Optional[Path], 
        flags: list[str], 
        analyzer: CMakeAnalyzer, 
        package_manager: str,
        jobs: int = 1
    ):
        self.project_root = Path(__file__).resolve().parents[2]
        self.root = (self.project_root / root).resolve() if not root.is_absolute() else root.resolve()
        self.build_path = self.root / "build"
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
        self.other_flags: set[str] = set()
        self.resolver = DependencyResolver()
        self.test_time: list[float] = []

    def set_enable_testing(self, enable_testing_path: Path) -> None:
        self.root = self.root
        self.test_path = Path(self.build_path, enable_testing_path)

    def set_flags(self, flags: list[str]) -> None:
        self.flags = flags

    def set_docker(self, docker_image: str, new: bool):
        self.docker = DockerManager(self.root, docker_image, new)

    def start_docker_image(self, container_name: str, new: bool = True) -> None:
        if not self.docker_image:
            self.docker_image = self.analyzer.get_docker()
        logging.info(f"Docker Version {self.docker_image}")
        self.set_docker(self.docker_image, new)
        self.docker.start_docker_container(container_name)
        self.container = self.docker.container

    def save_docker_image(self, repo_id: str, sha: str) -> None:
        image_name = ("_".join(repo_id.split("/")) + f"_{sha}").lower()
        container_id = self.container.id if self.container and self.container.id else "test"
        subprocess.run(["docker", "commit", container_id, image_name])
        subprocess.run(["docker", "save", image_name, "-o", f"{image_name}.tar"])

############### RUNNING ###############
        
    def configure(self) -> bool:
        return self._configure()

    def build(self) -> bool:
        if self.package_manager:
            return self._configure() and self._build()
        else:
            return self._configure_with_retries() and self._build()
    
    def test(self, test_exec: list[str], warmup: int = 0, test_repeat: int = 1) -> bool:
        return self._ctest(test_exec, warmup, test_repeat)
    
############### CONFIGURATION ###############
    
    def _configure_with_retries(self, max_retries: int = 5) -> bool:
        save_dependencies = set()
        unresolved_dependencies: set[str] = set() 

        if not self.container:
            logging.error(f"No docker container started")
            return False

        for attempt in range(max_retries):
            logging.info(f"[Attempt {attempt}/{max_retries}] Configuring project at {self.root}")

            if attempt == 0:
                missing_dependencies = self.analyzer.get_dependencies()
                unresolv, oflags = self.resolver.resolve_all(missing_dependencies, self.container)
                unresolved_dependencies |= unresolv
                self.other_flags |= oflags

            if self._configure():
                return True
            
            missing_dependencies = self.resolver.package_handler.get_missing_dependencies(
                self.config_stdout, 
                self.config_stderr, 
                Path(self.build_path) / "CMakeCache.txt"
            )

            if not missing_dependencies:
                logging.error("Configuration failed but no missing dependencies detected")
                break
            
            if missing_dependencies <= save_dependencies:
                logging.error("Configuration failed but no new missing dependencies detected")
                break 

            unresolv, oflags = self.resolver.resolve_all(missing_dependencies, self.container)
            unresolved_dependencies |= unresolv
            self.other_flags |= oflags
            
            if unresolved_dependencies:
                unresolved_dependencies, oflags = self.resolver.unresolved_dep(unresolved_dependencies)
                self.other_flags |= oflags

            save_dependencies |= missing_dependencies

        logging.error("All configuration attempts failed.")
        return False
    

    def _configure(self) -> bool:
        cmd = [
            'cmake', 
            '-S', self.to_container_path(self.root), 
            '-B', self.to_container_path(self.build_path), 
            '-G', 'Ninja',

            '-DCMAKE_TOOLCHAIN_FILE=/opt/vcpkg/scripts/buildsystems/vcpkg.cmake',
            #'-DVCPKG_MANIFEST_MODE=ON',
            #'-DVCPKG_MANIFEST_DIR=' + self.root,  # vcpkg.json location
            #'-DVCPKG_INSTALLED_DIR=' + str(Path(self.build_path) / 'vcpkg_installed'),  # isolate deps per build
            
            '-DCMAKE_BUILD_TYPE=Debug',
            '-DCMAKE_C_COMPILER=/usr/bin/clang',
            '-DCMAKE_CXX_COMPILER=/usr/bin/clang++',
            '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',

            #'-DCMAKE_C_FLAGS=-fprofile-instr-generate -fcoverage-mapping -O0 -g',
            #'-DCMAKE_CXX_FLAGS=-fprofile-instr-generate -fcoverage-mapping -O0 -g',
            #'-DCMAKE_EXE_LINKER_FLAGS=-fprofile-instr-generate',
            '-DCMAKE_C_COMPILER_LAUNCHER=ccache',
            '-DCMAKE_CXX_COMPILER_LAUNCHER=ccache',

            #'-DCMAKE_VERBOSE_MAKEFILE=ON',
            #'-DCMAKE_FIND_DEBUG_MODE=ON',
        ]

        for flag in self.flags:
            if 'disable' in flag.lower():
                cmd.append(f'-D{flag}=OFF')
            else:
                cmd.append(f'-D{flag}=ON')

        for flag in self.other_flags:
            cmd.append(flag)
        
        if self.package_manager.startswith("vcpkg"):
            logging.info("Installing through package manager vcpkg...")
            cmd.append('-DVCPKG_MANIFEST_MODE=ON')
        elif self.package_manager.startswith("conanfile"):
            # TODO: test this
            try:
                logging.info("Installing through package manager conan...")
                install = ['conan', 'install', '.', '-build=missing'] 
                exit_code, stdout, stderr = self.docker._run_command_in_docker(install, workdir=self.root, check=False)
                if exit_code == 0:
                    logging.info(f"Conan Output:\n{stdout}")
                else:
                    logging.error(f"Conan Output (stdout):\n{stdout}")
                    logging.error(f"Conan Error (stderr):\n{stderr}")
                    return False
            except Exception as e:
                logging.error(f"Conan installation failed: {e}")
                return False
            
        logging.info(" ".join(map(str, cmd)))
        exit_code, stdout, stderr = self.docker._run_command_in_docker(cmd, check=False)

        if exit_code == 0:
            logging.info(f"CMake Configuration successful for {self.build_path}")
            logging.info(f"Output:\n{stdout}")
            return True
        else:
            logging.error(f"CMake configuration failed for {self.build_path} (return code {exit_code})", exc_info=True)
            self.config_stdout = stdout
            self.config_stderr = stderr
            logging.error(f"Output (stdout):\n{stdout}")
            logging.error(f"Error (stderr):\n{stderr}")
            return False

############### BUILDING ###############

    def _build(self) -> bool:
        cmd = ['cmake', '--build', self.to_container_path(self.build_path), '--']
        if self.jobs > 0:
            cmd += ['-j', str(self.jobs)]

        logging.info(" ".join(map(str, cmd)))
        exit_code, stdout, stderr = self.docker._run_command_in_docker(cmd, check=False)
        
        if exit_code == 0:
            logging.info(f"CMake build completed for {self.root}")
            logging.info(f"Output:\n{stdout}")
            return True
        else:
            logging.error(f"CMake build failed for {self.root} (return code {exit_code})", exc_info=True)
            self.build_stdout = stdout
            self.build_stderr = stderr
            logging.error(f"Output (stdout):\n{stdout}", exc_info=True)
            logging.error(f"Error (stderr):\n{stderr}", exc_info=True)
            return False

############### TESTING ###############

    # TODO: ensure that the tests are each run in isolation
    # check CTestTestfile.cmake -> check add_test(some_name path/to/executable)
    # use path/to/executable 
    #      Catch2   => --list-tests 
    #      GTest    => --gtest_list_tests
    #      doctest  => --list-test-cases
    #      add_test => probably just scanning all add_test(some_name path/to/executable)
    #                   and take path/to/executable as unit test
    def _ctest(self, test_exec: list[str], warmup: int = 0, test_repeat: int = 1) -> bool:
        if test_repeat < 1:
            return True
        
        test_dir = Path(self.test_path)
        if test_exec:
            self._isolated_ctest(test_exec)
        cmd = ['ctest', '--output-on-failure', '--fail-if-no-tests']
        
        try:
            exit_code, stdout, stderr = self.docker._run_command_in_docker(
                ['ctest', '--help'], workdir=self.test_path, check=False
            )
            if '--fail-if-no-tests' not in stdout:
                # Fallback for older CMake versions: check if any tests exist
                check_cmd = ['ctest', '-N']
                exit_code, stdout_check, _ = self.docker._run_command_in_docker(
                    check_cmd, workdir=self.test_path, check=False
                )
                if 'No tests were found' in stdout_check or 'Test #' not in stdout_check:
                    logging.error(f"No tests found in {self.test_path}")
                    return False
                
                cmd = ['ctest', '--output-on-failure']

            elapsed_times: list[float] = []
            for i in range(warmup + test_repeat):
                logging.info(f"{' '.join(map(str, cmd))} in {self.test_path}")
                exit_code, stdout, stderr = self.docker._run_command_in_docker(
                    cmd, workdir=self.test_path, check=False
                )
                stats = self.analyzer.parse_ctest_output(stdout)
                elapsed: float = stats['total_time_sec']
                elapsed_times.append(elapsed)

                if exit_code == 0:
                    logging.info(f"CTest passed for {self.test_path}")
                    logging.info(f"Output:\n{stdout}")
                    logging.info(f"Tests run: {stats['total']}, Failures: {stats['failed']}, Skipped: {stats['skipped']}, Time elapsed: {elapsed} s")
                else:
                    logging.error(f"CTest failed for {self.test_path} (return code {exit_code})", exc_info=True)
                    logging.error(f"Output (stdout):\n{stdout}", exc_info=True)
                    logging.error(f"Error (stderr):\n{stderr}", exc_info=True)
                    return False
            
            self.test_time = elapsed_times
            return True
            
        except Exception as e:
            logging.error(f"CTest execution failed: {e}", exc_info=True)
            return False

    def _isolated_ctest(self, test_exec: list[str]) -> bool:
        test_dir = Path(self.test_path)
        list_test_arg = self.analyzer.get_list_test_arg()[0]
        unit_tests: dict[str, list[str]] = {}
        for exec in test_exec:
            cmd = [exec, list_test_arg]
            try:
                logging.info(f"{' '.join(map(str, cmd))} {list_test_arg}")
                result = subprocess.run(cmd, cwd=test_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                logging.info(f"CTest Output: {result.stdout}")
                unit_tests[exec] = self.analyzer.parser.find_unit_tests(result.stdout)
            except subprocess.CalledProcessError as e:
                logging.error(f"{' '.join(map(str, cmd))} {list_test_arg} couldn't list unit tests (return code {e.returncode})", exc_info=True)
                logging.error(f"Output (stdout):\n{e.stdout}", exc_info=True)
                logging.error(f"Error (stderr):\n{e.stderr}", exc_info=True)
        for exec, tests in unit_tests.items():
            for test in tests:
                # TODO: run this tests, each with different profile
                cmd = ['LLVM_PROFILE_FILE=coverage/%t.profraw', exec, test]
                try:
                    result = subprocess.run(cmd, cwd=test_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                except:
                    logging.error("", exc_info=True)
                    # TODO: extract the profraw coverage without the test and build folders
            # TODO: extract coverage data and create
        return False
    
    def to_container_path(self, path: Path) -> str:
        rel = path.relative_to(self.root.parent)
        return f"/workspace/{rel.as_posix()}"
    

class GitHandler:
    def _get_default_branch(self, repo_url: str) -> str:
        result = subprocess.run(
            ["git", "ls-remote", "--symref", repo_url, "HEAD"],
            capture_output=True, text=True
        )

        for line in result.stdout.splitlines():
            if line.startswith("ref:"):
                return line.split()[1].split("/")[-1]
        return "main" 

    def clone_repo(self, repo_id: str, repo_path: Path, branch: str = "main", sha: str = "") -> bool:
        url = f"https://github.com/{repo_id}.git"
        
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        
        if sha:
            logging.info(f"Cloning repository {url} for commit {sha} into {repo_path}")
            try:
                subprocess.run(
                    ["git", "config", "--global", "--add", "safe.directory", "*"],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )

                subprocess.run(
                    ["git", "clone", "--depth=1", url, repo_path],
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                
                subprocess.run(
                    ["git", "fetch", "--depth=1", "origin", sha],
                    cwd=repo_path,
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                
                subprocess.run(
                    ["git", "checkout", sha],
                    cwd=repo_path,
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                
                subprocess.run(
                    ["git", "submodule", "update", "--init", "--recursive", "--depth=1"],
                    cwd=repo_path,
                    check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                
                logging.info(f"Repository checked out to commit {sha} successfully")
                return True
                
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to clone/checkout commit {sha}", exc_info=True)
                logging.error(f"Output (stdout):\n{e.stdout}")
                logging.error(f"Error (stderr):\n{e.stderr}")
                return False

        if branch == "main":
            branch = self._get_default_branch(url)
        
        logging.info(f"Cloning repository {url} (branch: {branch}) into {repo_path}")
        try:
            result = subprocess.run(
                ["git", "clone", "--recurse-submodules", "--shallow-submodules", 
                 "--branch", branch, "--depth=1", url, repo_path], 
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            logging.info(f"Repository cloned successfully")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to clone repository {url} (branch: {branch})", exc_info=True)
            logging.error(f"Output (stdout):\n{e.stdout}")
            logging.error(f"Error (stderr):\n{e.stderr}")
            return False
        
        
class DockerManager:
    def __init__(self, root: Path, docker_image: str, new: bool):
        self.root = root
        self.docker_image = docker_image
        self.new = new

    def stop_container(self) -> None:
        if self.container:
            self.container.stop()
            self.container.remove()
            self.container = None

    def start_docker_container(self, container_name: str) -> None:
        client = docker.from_env()
        try:
            try:
                self.container = client.containers.get(container_name)
                logging.info(f"Reusing existing container {container_name}")
                return
            except docker.errors.NotFound: # type: ignore
                pass
            
            mount = Mount(
                target="/workspace", source=str(self.root.parent), type="bind", read_only=False
            )
            self.container = client.containers.run(
                self.docker_image,
                command=["sleep", "infinity"],
                name=container_name,
                mounts=[mount],
                working_dir="/workspace",
                detach=True,
                tty=True,
                remove=False
            )
        except Exception as e:
            logging.error(f"Docker execution failed: {e}")

    def _run_command_in_docker(self, cmd, workdir: Optional[Path] = None, check: bool = True) -> tuple[int, str, str]:
        """Run command in Docker container if docker_image is set, otherwise locally"""
        if not self.docker_image:
            try:
                result = subprocess.run(cmd, cwd=workdir or self.root, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                return result.returncode, result.stdout, result.stderr
            except subprocess.CalledProcessError as e:
                return e.returncode, e.stdout, e.stderr
            
        rel_root = os.path.relpath(self.root, self.root.parent)
        container_root = posixpath.join("/workspace", rel_root.replace("\\", "/"))

        if workdir:
            rel_workdir = os.path.relpath(workdir, self.root.parent).replace("\\", "/")
            container_workdir = posixpath.join("/workspace", rel_workdir)
        else:
            container_workdir = container_root
        
        if not self.container:
            logging.error(f"No docker container started")
            return 1, "", ""

        cmd = [str(x) for x in cmd]
        exit_code, output = self.container.exec_run(cmd, workdir=str(container_workdir))
        output = output.decode(errors="ignore") if output else ""
        self.container.exec_run(["bash", "-c", f"echo '{output}' >> /workspace/logs/{'new' if self.new else 'old'}.log"])
        logs = self.container.logs().decode()
        return exit_code, output, logs
