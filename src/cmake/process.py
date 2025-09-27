
import logging, subprocess, os, shutil, re
from pathlib import Path
from src.cmake.analyzer import CMakeAnalyzer
from typing import Optional
from src.cmake.package import CMakePackageHandler

class CMakeProcess:
    """Class configures, builds and tests commits."""
    def __init__(self, root: str, build: str, test: str, jobs: int = 1, analyzer: Optional[CMakeAnalyzer] = None):
        self.root = root
        self.build_path = build
        self.test_path = test
        self.jobs = jobs

        self.analyzer = analyzer if analyzer is not None else CMakeAnalyzer(self.root)
        self.flags = self.analyzer.has_build_testing_flag()
        #self.flags_info = CMakeProcessAnalyzer(self.root).analyze_flags()

    def build(self) -> bool:
        package_handler = CMakePackageHandler(self.analyzer)
        package_handler.packages_installer()
        return self._configure() and self._cmake()
    
    def test(self) -> bool:
        return self._ctest()

    def _configure(self) -> bool:
        # TODO: maybe no optimization, gcovr + llvm coverage information
        cmakelists = Path(self.root) / "CMakeLists.txt"
        needs_old_policy = False
        if cmakelists.exists():
            text = cmakelists.read_text()
            match = re.search(r"cmake_minimum_required\s*\(VERSION\s*([0-9.]+)", text, re.I)
            if match:
                version = tuple(map(int, match.group(1).split(".")))
                if version < (3, 5):
                    needs_old_policy = True

        cmd = ['cmake', '-S', self.root, '-B', self.build_path, 
               #f'-DCMAKE_BUILD_TYPE=Release',
               '-DCMAKE_C_COMPILER=clang',
               '-DCMAKE_BUILD_TYPE=Debug',
               '-DCMAKE_CXX_COMPILER=clang++',
               '-DCMAKE_CXX_FLAGS=--coverage -O0 -g',
               '-DCMAKE_EXE_LINKER_FLAGS=--coverage'
        ]

        if needs_old_policy:
            logging.info("CMake needs olf policy, setting CMAKE_POLICY_VERSION_MINIMUM=3.5")
            cmd.append("-DCMAKE_POLICY_VERSION_MINIMUM=3.5")

        for flag in self.flags.keys():
            if 'disable' in flag.lower():
                cmd.append(f'-D{flag}=OFF')
            else:
                cmd.append(f'-D{flag}=ON')
        
        try:
            logging.info(f"Configure CMake: {cmd}")
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logging.info(f"CMake configured {self.build_path} successfully:\n{result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"CMake configuration failed for {self.build_path}.\nReturn code: {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}", exc_info=True)
            return False

    
    def _cmake(self) -> bool:
        cmd = ['cmake', '--build', self.build_path]
        if self.jobs > 0:
            cmd += ['-j', str(self.jobs)]
        try:
            logging.info(f"Build CMake: {cmd}")
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logging.info(f"CMake build completed for {self.root}:\n{result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"CMake build failed for {self.root}.\nReturn code: {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}", exc_info=True)
            return False

    # TODO: ensure that the tests are each run in isolation
    # check CTestTestfile.cmake -> check add_test(some_name path/to/executable)
    # use path/to/executable 
    #      Catch2   => --list-tests 
    #      GTest    => --gtest_list_tests
    #      doctest  => --list-test-cases
    #      add_test => probably just scanning all add_test(some_name path/to/executable)
    #                   and take path/to/executable as unit test
    def _ctest(self) -> bool:
        test_dir = Path(self.test_path)
        cmd = ['ctest', '--output-on-failure']
        try:
            logging.info(f"CTest: {cmd} in {self.test_path}")
            result = subprocess.run(cmd, cwd=test_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logging.info(f"CMake tests passed for {self.test_path}\n{result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"CMake tests failed for {self.test_path}.\nReturn code: {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}", exc_info=True)
            return False
        
    def _get_default_branch(self, repo_url: str):
        result = subprocess.run(
            ["git", "ls-remote", "--symref", repo_url, "HEAD"],
            capture_output=True, text=True, check=True
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
            logging.info(f"Repository cloned successfully:\n{result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to clone repository {url} (branch: {branch}) into {repo_path}.\nReturn code: {e.returncode}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}", exc_info=True)
            return False


class CMakeProcessAnalyzer:
    """Class used for analyzing CMakeLists.txt by running subprocess."""
    def __init__(self, root: str):
        self.root = root

    def analyze_flags(self) -> str:
        repo_root = Path(self.root)
        build_dir = repo_root / "build"
        build_dir.mkdir(exist_ok=True)

        logging.info(f"Configuring project at {repo_root}.")
        try:
            result_config = subprocess.run(["cmake", ".."], cwd=build_dir, capture_output=True, text=True, check=True)
            logging.info(f"CMake configure output:\n{result_config.stdout}")
        except subprocess.CalledProcessError as e:
            logging.error(f"FAILED: cmake configure at {repo_root}")
            logging.error(f"stderr:\n{e.stderr}")
            return ""
        
        logging.info(f"Querying cached variables with 'cmake -LH'")
        try:
            result_flags = subprocess.run(["cmake", "-LH", ".."], cwd=build_dir, capture_output=True, text=True, check=True)
            logging.info(f"CMake -LH output:\n{result_flags.stdout}")
            return result_flags.stdout
        except subprocess.CalledProcessError as e:
            logging.error(f"FAILED: cmake -LH at {repo_root}")
            logging.error(f"stderr:\n{e.stderr}")
            return ""