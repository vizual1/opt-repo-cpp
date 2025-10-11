
import logging, subprocess, os, shutil, re
from pathlib import Path
from src.cmake.analyzer import CMakeAnalyzer
from src.cmake.autobuilder import CMakeAutoBuilder
from src.cmake.package import CMakePackageHandler
#import src.config as conf

vcpkg_pc = "/opt/vcpkg/installed/x64-linux/lib/pkgconfig"
os.environ["PKG_CONFIG_PATH"] = f"{vcpkg_pc}:{os.environ.get('PKG_CONFIG_PATH','')}"

class CMakeProcess:
    """Class configures, builds, tests, and clones commits."""
    def __init__(self, root: str, build: str, test: str, flags: list[str], analyzer: CMakeAnalyzer, jobs: int = 1):
        self.root = root
        self.build_path = build
        self.test_path = test
        self.jobs = jobs
        self.flags: list[str] = flags
        self.analyzer = analyzer
        self.config_stdout: str = ""
        self.config_stderr: str = ""
        self.build_stdout: str = ""
        self.other_flags: set[str] = set()
        self.auto_builder = CMakeAutoBuilder(self.root)
        self.package_handler = CMakePackageHandler(self.analyzer)
        
    def configure(self) -> bool:
        return self._configure_with_retries()

    def build(self) -> bool:
        return self._configure_with_retries() and self._build()
    
    def test(self, test_exec: list[str]) -> bool:
        return self._ctest(test_exec)
    
############### CONFIGURATION ###############
    
    def _configure_with_retries(self, max_retries: int = 5) -> bool:
        save_dependencies = set()
        for attempt in range(max_retries):
            logging.info(f"[Attempt {attempt}/{max_retries}] Configuring project at {self.root}")

            if self._configure():
                return True
            
            missing_dependencies = self.package_handler.get_missing_dependencies(
                self.config_stdout, 
                self.config_stderr, 
                Path(self.build_path) / "CMakeCache.txt"
            )
            if not missing_dependencies:
                logging.error("Configuration failed but no missing dependencies detected")
                break
            
            if missing_dependencies in save_dependencies:
                logging.error("Configuration failed but no new missing dependencies detected")
                break   

            #self.auto_builder.add_to_manifest(missing_dependencies)
            #if attempt == 0:
            #    missing_dependencies |= self.analyzer.get_dependencies()
            
            for dep in missing_dependencies:
                try:
                    subprocess.run(["/opt/vcpkg/vcpkg", "install", dep.lower()], check=True)
                    self.auto_builder.inject_vcpkg_dependency(dep)
                    self.other_flags |= self.auto_builder.flags
                    logging.info(f"Installed {dep}")
                except subprocess.CalledProcessError as e:
                    logging.warning(f"Failed to install {dep}: {e}")
                except Exception as e:
                    logging.error(f"Unexpected error with {dep}: {e}")
            
            save_dependencies = missing_dependencies.copy()
             
        logging.info("Try LLM...")
        response: str = self.package_handler.llm_prompt(errors=self.config_stderr[:200])
        logging.info(f"{response}")
        for cmd in response.split("\n"):
            try:
                subprocess.run([cmd.replace("sudo", "")], check=True)
                self.auto_builder.inject_vcpkg_dependency(dep)
                self.other_flags |= self.auto_builder.flags
                logging.info(f"Installed with {cmd}")
            except subprocess.CalledProcessError as e:
                logging.warning(f"Failed to install {cmd}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error with {cmd}: {e}")
        if self._configure():
            return True
        
        logging.error("All configuration attempts failed.")
        return False

    def _configure(self) -> bool:
        cmd = [
            'cmake', 
            '-S', self.root, 
            '-B', self.build_path, 
            '-G', 'Ninja',

            '-DCMAKE_TOOLCHAIN_FILE=/opt/vcpkg/scripts/buildsystems/vcpkg.cmake',
            #'-DVCPKG_MANIFEST_MODE=ON',
            #'-DVCPKG_MANIFEST_DIR=' + self.root,  # vcpkg.json location
            #'-DVCPKG_INSTALLED_DIR=' + str(Path(self.build_path) / 'vcpkg_installed'),  # isolate deps per build
            
            '-DCMAKE_BUILD_TYPE=Debug',
            '-DCMAKE_C_COMPILER=/usr/bin/clang-16',
            '-DCMAKE_CXX_COMPILER=/usr/bin/clang++-16',

            '-DCMAKE_C_FLAGS=-fprofile-instr-generate -fcoverage-mapping -O0 -g',
            '-DCMAKE_CXX_FLAGS=-fprofile-instr-generate -fcoverage-mapping -O0 -g',
            '-DCMAKE_EXE_LINKER_FLAGS=-fprofile-instr-generate',
            
            '-DCMAKE_C_COMPILER_LAUNCHER=ccache',
            '-DCMAKE_CXX_COMPILER_LAUNCHER=ccache',

            '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
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
        
        try:
            logging.info(f"{' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logging.info(f"CMake Configuration successful for {self.build_path}")
            logging.info(f"Output:\n{result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"CMake configuration failed for {self.build_path} (return code {e.returncode})", exc_info=True)
            self.config_stdout = e.stdout if e.stdout else ""
            self.config_stderr = e.stderr if e.stderr else ""
            logging.error(f"Output (stdout):\n{e.stdout}")
            logging.error(f"Error (stderr):\n{e.stderr}")
            return False

############### BUILDING ###############

    # TODO:
    def _build_with_retries(self, max_retries: int = 3) -> bool:
        for attempt in range(max_retries):
            logging.info(f"[Attempt {attempt}/{max_retries}] Building project at {self.root}")
            if self._build():
                return True
            logging.warning("Build failed. Attempting recovery and retry...")
            self._analyze_build_failure() 
        logging.error("All build attempts failed.")
        return False
    
    def _analyze_build_failure(self):
        """Try to automatically handle common build failures."""
        missing_header = re.findall(r"fatal error: ([\w\/\.\-]+): No such file or directory", self.build_stdout)
        if missing_header:
            for header in missing_header:
                pkg = header.split('/')[0]
                logging.warning(f"Missing header detected: {header} -> guessing package '{pkg}'")
                subprocess.run(["/opt/vcpkg/vcpkg", "install", pkg])

        if "undefined reference to" in self.build_stdout:
            symbols = re.findall(r"undefined reference to [`']([\w:]+)[`']", self.build_stdout)
            if symbols:
                logging.warning(f"Detected linker symbols: {symbols[:3]}{'...' if len(symbols) > 3 else ''}")
            # Optionally try to detect missing libraries via `pkg-config --list-all`

        if "No rule to make target" in self.build_stdout or "file not found" in self.build_stdout:
            logging.info("Possible parallel build race condition: retrying single-threaded build...")
            subprocess.run(['cmake', '--build', self.build_path, '-j1'])


    def _build(self) -> bool:
        cmd = ['cmake', '--build', self.build_path, '--']
        if self.jobs > 0:
            cmd += ['-j', str(self.jobs)]
        cmd += ['-k', '0'] 
        try:
            logging.info(f"{' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logging.info(f"CMake build completed for {self.root}")
            logging.info(f"Output:\n{result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"CMake build failed for {self.root} (return code {e.returncode})", exc_info=True)
            logging.error(f"Output (stdout):\n{e.stdout}", exc_info=True)
            logging.error(f"Error (stderr):\n{e.stderr}", exc_info=True)
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
    def _ctest(self, test_exec: list[str]) -> bool:
        test_dir = Path(self.test_path)
        if test_exec:
            self._isolated_ctest(test_exec)

        cmd = ['ctest', '--output-on-failure']
        try:
            logging.info(f"{' '.join(cmd)} in {self.test_path}")
            result = subprocess.run(cmd, cwd=test_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logging.info(f"CTest passed for {self.test_path}")
            logging.info(f"Output:\n{result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"CTest failed for {self.test_path} (return code {e.returncode})", exc_info=True)
            logging.error(f"Output (stdout):\n{e.stdout}", exc_info=True)
            logging.error(f"Error (stderr):\n{e.stderr}", exc_info=True)
        except FileNotFoundError as e:
            logging.error(f"FileNotFoundError: {e}", exc_info=True)
        return False
        
    
    # TODO
    def _isolated_ctest(self, test_exec: list[str]) -> bool:
        test_dir = Path(self.test_path)
        list_test_arg = self.analyzer.get_list_test_arg()[0]
        unit_tests: dict[str, list[str]] = {}
        for exec in test_exec:
            cmd = [exec, list_test_arg]
            try:
                logging.info(f"{' '.join(cmd)} {list_test_arg}")
                result = subprocess.run(cmd, cwd=test_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                logging.info(f"CTest Output: {result.stdout}")
                unit_tests[exec] = self.analyzer.parser.find_unit_tests(result.stdout)
            except subprocess.CalledProcessError as e:
                logging.error(f"{' '.join(cmd)} {list_test_arg} couldn't list unit tests (return code {e.returncode})", exc_info=True)
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
    
############### CLONING ###############

    def _get_default_branch(self, repo_url: str):
        result = subprocess.run(
            ["git", "ls-remote", "--symref", repo_url, "HEAD"],
            capture_output=True, text=True
        )

        for line in result.stdout.splitlines():
            if line.startswith("ref:"):
                return line.split()[1].split("/")[-1]
        return "main" 
        
    def clone_repo(self, repo_id: str, repo_path: str, branch: str = "main") -> bool:
        url = f"https://github.com/{repo_id}.git"
        if branch == "main":
            branch = self._get_default_branch(url)
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        cmd = ["git", "clone", "--recurse-submodules", "--shallow-submodules", "--branch", branch, f"--depth=1", url, repo_path]
        logging.info(f"Cloning repository {url} (branch: {branch}) into {repo_path}")
        try:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logging.info(f"Repository cloned successfully")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to clone repository {url} (branch: {branch}) into {repo_path} (return code {e.returncode})", exc_info=True)
            logging.error(f"Output (stdout):\n{e.stdout}", exc_info=True)
            logging.error(f"Error (stderr):\n{e.stderr}", exc_info=True)
            return False
