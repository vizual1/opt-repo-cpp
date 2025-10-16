
import logging, subprocess, os, shutil, json, time
from pathlib import Path
from src.cmake.analyzer import CMakeAnalyzer
#from src.cmake.autobuilder import CMakeAutoBuilder
#from src.cmake.package import CMakePackageHandler
from src.cmake.resolver import DependencyResolver
from typing import Any
#import src.config as conf

vcpkg_pc = "/opt/vcpkg/installed/x64-linux/lib/pkgconfig"
os.environ["PKG_CONFIG_PATH"] = f"{vcpkg_pc}:{os.environ.get('PKG_CONFIG_PATH','')}"

class CMakeProcess:
    """Class configures, builds, tests, and clones commits."""
    def __init__(self, root: str, build: str, test: str, 
                 flags: list[str], analyzer: CMakeAnalyzer, package_manager: str, jobs: int = 1):
        self.root = root
        self.build_path = build
        self.test_path = test
        
        self.flags: list[str] = flags
        self.analyzer = analyzer
        self.package_manager = package_manager
        self.jobs = jobs

        self.config_stdout: str = ""
        self.config_stderr: str = ""
        self.build_stdout: str = ""
        self.build_stderr: str = ""
        self.other_flags: set[str] = set()

        #self.auto_builder = CMakeAutoBuilder(self.root)
        #self.package_handler = CMakePackageHandler(self.analyzer)
        self.resolver = DependencyResolver()
        self.test_time: float = 0.0
        
    def configure(self) -> bool:
        return self._configure()

    def build(self) -> bool:
        # TODO: _configure()
        # vcpkg.json -> set to manifest mode?
        # conanfiles.txt or conanfiles.py -> conan install . --build=missing?
        # no package_handler -> _configure_with_retries()
        #return self._configure_with_retries() and self._build()
        if self.package_manager:
            return self._configure() and self._build()
        else:
            return self._configure_with_retries() and self._build()
    
    def test(self, test_exec: list[str], test_repeat: int = 1) -> bool:
        return self._ctest(test_exec, test_repeat)
    
############### CONFIGURATION ###############
    
    def _configure_with_retries(self, max_retries: int = 5) -> bool:
        save_dependencies = set()
        for attempt in range(max_retries):
            logging.info(f"[Attempt {attempt}/{max_retries}] Configuring project at {self.root}")

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
            
            if missing_dependencies in save_dependencies:
                logging.error("Configuration failed but no new missing dependencies detected")
                break   

            if attempt == 0:
                missing_dependencies |= self.analyzer.get_dependencies()
            
            unresolved_dependencies: set[str] = set() 
            for dep in missing_dependencies:
                resolve = self.resolver.resolve(dep.lower())
                if not resolve:
                    unresolved_dependencies.add(dep)
                    logging.warning(f"Unresolved dependency {dep}")
                    continue
                
                dep = dep.lower()
                if self.resolver.install(dep, method="apt"):
                    self.other_flags |= self.resolver.flags(dep, method="apt")
                elif self.resolver.install(dep, method="vcpkg"):
                    self.resolver.cache.mapping[dep]["apt"] = ""
                    self.other_flags |= self.resolver.flags(dep, method="vcpkg")
                else:
                    self.resolver.cache.mapping[dep]["apt"] = ""
                    self.resolver.cache.mapping[dep]["vcpkg"] = ""
                self.resolver.cache.save()
            
            if unresolved_dependencies:
                logging.info(f"All unresolved dependencies {unresolved_dependencies}")
                llm_output = self.resolver.llm.llm_prompt(list(unresolved_dependencies), timeout=60)
                logging.info(f"LLM prompt returned:\n{llm_output}")
                try:
                    data: dict[str, dict[str, Any]] = json.loads(llm_output)
                    data = {k.lower() if isinstance(k, str) else k: v for k, v in data.items()}
                    for dep in unresolved_dependencies:
                        resolve = self.resolver.resolve(dep.lower())
                        if not resolve:
                            logging.warning(f"Failed to resolve {dep} (invalid dependency or wrong LLM output)")
                            continue
                        
                        dep.lower()
                        if self.resolver.install(dep, method="apt"):
                            self.other_flags |= self.resolver.flags(dep, method="apt")
                        elif self.resolver.install(dep, method="vcpkg"):
                            data[dep]["apt"] = ""
                            self.other_flags |= self.resolver.flags(dep, method="vcpkg")
                        else:
                            data[dep]["apt"] = ""
                            data[dep]["vcpkg"] = ""

                    self.resolver.cache.mapping.update(data)
                    self.resolver.cache.save()
                    logging.info(f"Added {data.keys()} to dependency cache")
                except json.JSONDecodeError as e:
                    logging.error(f"Invalid JSON for {llm_output}: {e}")

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
            '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',

            '-DCMAKE_C_FLAGS=-fprofile-instr-generate -fcoverage-mapping -O0 -g',
            '-DCMAKE_CXX_FLAGS=-fprofile-instr-generate -fcoverage-mapping -O0 -g',
            '-DCMAKE_EXE_LINKER_FLAGS=-fprofile-instr-generate',
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
            cmd.append('-DVCPKG_MANIFEST_MODE=ON')
        elif self.package_manager.startswith("conanfile"):
            logging.info("Installing through package manager conan...")
            install = ['conan', 'install', '.', '-build=missing'] 
            result = subprocess.run(install, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
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

    def _build(self) -> bool:
        cmd = ['cmake', '--build', self.build_path, '--']
        if self.jobs > 0:
            cmd += ['-j', str(self.jobs)]
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
    def _ctest(self, test_exec: list[str], test_repeat: int) -> bool:
        test_dir = Path(self.test_path)
        if test_exec:
            self._isolated_ctest(test_exec)

        cmd = ['ctest', '--output-on-failure']

        start_time = time.perf_counter()
        try:
            for _ in range(test_repeat):
                logging.info(f"{' '.join(cmd)} in {self.test_path}")
                result = subprocess.run(cmd, cwd=test_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                elapsed = time.perf_counter() - start_time
                self.test_time += elapsed
                logging.info(f"CTest passed for {self.test_path}")
                logging.info(f"Output:\n{result.stdout}")
                logging.info(f"Measured time: {elapsed}")
            self.test_time /= test_repeat
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
        
    def _clone_repo(self, repo_id: str, repo_path: str, branch: str = "main") -> bool:
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


    def clone_repo(self, repo_id: str, repo_path: str, branch: str = "main", sha: str = "") -> bool:
        url = f"https://github.com/{repo_id}.git"
        
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        
        if sha:
            logging.info(f"Cloning repository {url} for commit {sha} into {repo_path}")
            try:
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
        else:
            if branch == "main":
                branch = self._get_default_branch(url)
            
            cmd = ["git", "clone", "--recurse-submodules", "--shallow-submodules", 
                        "--branch", branch, "--depth=1", url, repo_path]
            logging.info(f"Cloning repository {url} (branch: {branch}) into {repo_path}")
            try:
                result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE, text=True)
                logging.info(f"Repository cloned successfully")
                return True
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to clone repository {url} (branch: {branch})", exc_info=True)
                logging.error(f"Output (stdout):\n{e.stdout}")
                logging.error(f"Error (stderr):\n{e.stderr}")
                return False