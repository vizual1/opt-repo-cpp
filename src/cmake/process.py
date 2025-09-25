
import logging, subprocess
from pathlib import Path
from src.cmake.analyzer import CMakeAnalyzer, CMakeFlagsAnalyzer

class CMakeProcess:
    def __init__(self, root: str, build: str, test: str, jobs: int = 1):
        self.root = root
        self.build = build
        self.test = test
        self.jobs = jobs
        # TODO: process?
        self.analyzer = CMakeAnalyzer(self.root)
        self.flags_dict = CMakeFlagsAnalyzer(self.root).analyze()
        self.flags_info = CMakeProcessAnalyzer(self.root).analyze_flags()
        logging.info(f"Flags information:\n{self.flags_info}")
        self.flags: list[tuple[str, str]] = []

    def run(self) -> None:
        self._configure()
        self._cmake()
        self._ctest()

    def _configure(self) -> None:
        # TODO: maybe no optimization
        cmd = ['cmake', '-S', self.root, '-B', self.build, f'-DCMAKE_BUILD_TYPE=Release']
        for flag, set in self.flags:
            cmd.append(f'-D{flag}={set}')
        try:
            logging.info(f"Configure CMake: {cmd}")
            subprocess.run(cmd, check=True)
            logging.info(f"CMake configured {self.build} successfully.")
        except subprocess.CalledProcessError:
            logging.error(f"CMake configuration failed for {self.build}.")

    def _cmake(self) -> None:
        cmd = ['cmake', '--build', self.build]
        if self.jobs > 0:
            cmd += ['-j', str(self.jobs)]
        try:
            logging.info(f"Build CMake: {cmd}")
            subprocess.run(cmd, check=True)
            logging.info(f"CMake build completed for {self.root}.")
        except subprocess.CalledProcessError:
            logging.error(f"CMake build failed for {self.root}.")

    def _ctest(self) -> None:
        test_dir = Path(self.test)
        cmd = ['ctest', '--output-on-failure']
        try:
            logging.info(f"CTest: {cmd} in {self.test}")
            result = subprocess.run(cmd, cwd=test_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logging.info(f"CMake tests passed for {self.test}")
            logging.info(result.stdout)
        except subprocess.CalledProcessError as e:
            logging.error(f"CMake tests failed for {self.test}")
            logging.info(e.stdout)
            

class CMakePackageHandler:
    def __init__(self, analyzer: CMakeAnalyzer):
        self.analyzer = analyzer
        self.packages = self._get_packages()

    def _get_packages(self) -> set[str]:
        deps = self.analyzer.get_dependencies()
        packages_needed = set()
        for dep in deps:
            # TODO: add cache load if exist otherwise find_apt_package and save
            pkg = self._find_apt_package(dep)
            if pkg:
                packages_needed.add(pkg)
        return packages_needed

    def _find_apt_package(self, cdep_name: str) -> str:
        """Find corresponding apt package from CMake dependency name."""
        try:
            logging.info(f"Trying to find_apt_package: {cdep_name}")
            result = subprocess.run(['apt-cache', 'search', cdep_name],
                                    capture_output=True, text=True, check=False)
            lines = result.stdout.splitlines()
            dev_packages = [line.split(' - ')[0] for line in lines if 'dev' in line]
            if dev_packages:
                logging.info(f"Found dev_packages for {cdep_name}: {dev_packages[0]}")
                return dev_packages[0]
        except FileNotFoundError:
            logging.error(f"No dev_packages for {cdep_name} found.")
            pass

        return ''

    def packages_installer(self) -> list[str]:
        result_packages = []
        for p in self.packages:
            if not self._is_package_installed(p):
                logging.info(f"Trying to install package {p}...")
                self._install_package(p)
            else:
                logging.info(f"Package {p} is already installed.")

        return result_packages

    def _is_package_installed(self, package: str) -> bool:
        try:
            result = subprocess.run(['dpkg', '-l'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return package in result.stdout
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            return False

    def _install_package(self, package: str) -> None:
        try:
            subprocess.run(['apt', 'install', '-y', package], check=True)
            logging.info(f"{package} has been installed.")
        except subprocess.CalledProcessError:
            logging.error(f"Failed to install {package}.")


class CMakeProcessAnalyzer:
    """Class used for analyzing CMakeLists.txt by running subprocess."""
    def __init__(self, root: str):
        self.root = root

    def analyze_flags(self) -> str:
        repo_root = Path(self.root)
        build_dir = repo_root / "build"
        build_dir.mkdir(exist_ok=True)

        logging.info(f"Configuring project at {repo_root}")
        try:
            result_config = subprocess.run(["cmake", str(repo_root)], cwd=build_dir, capture_output=True, text=True, check=True)
            logging.info(f"CMake configure output:\n{result_config.stdout}")
        except subprocess.CalledProcessError as e:
            logging.error(f"FAILED: cmake configure at {repo_root}")
            logging.error(f"stderr:\n{e.stderr}")
            return ""
        
        logging.info(f"Querying cached variables with 'cmake -LH'")
        try:
            result_flags = subprocess.run(["cmake", "-LH"], cwd=build_dir, capture_output=True, text=True, check=True)
            logging.info(f"CMake -LH output:\n{result_flags.stdout}")
            return result_flags.stdout
        except subprocess.CalledProcessError as e:
            logging.error(f"FAILED: cmake -LH at {repo_root}")
            logging.error(f"stderr:\n{e.stderr}")
            return ""