import logging, subprocess
from src.cmake.analyzer import CMakeAnalyzer
import src.config as conf

class CMakePackageHandler:
    def __init__(self, analyzer: CMakeAnalyzer):
        self.analyzer = analyzer
        self.packages, self.python = self._get_packages()

    def packages_installer(self) -> None:
        for p in self.packages:
            if not self._is_package_installed(p):
                logging.info(f"Installing package {p}...")
                self._install_package(p)
            else:
                logging.info(f"Package {p} already installed.")


    def _get_packages(self) -> tuple[set[str], set[str]]:
        deps = self.analyzer.get_dependencies()
        packages_needed = set()
        python_packages = set()
        for dep in deps:
            if dep.lower() in conf.SKIP_NAMES:
                logging.debug(f"{dep} is skipped.")
                continue

            if dep in conf.NON_APT:
                logging.warning(f"{dep} is not an apt package: {conf.NON_APT[dep]}.")
                continue

            pkg = self._find_apt_package(dep)
            if pkg:
                packages_needed.add(pkg)

        return packages_needed, python_packages

    def _find_apt_package(self, dep: str) -> str:
        """Resolve dependency for apt package using multiple strategies."""
        logging.info(f"Resolving dependency: {dep}")

        # 1. mapping table:
        if dep in conf.PACKAGE_MAP:
            logging.info(f"Mapping table hit: {dep} -> {conf.PACKAGE_MAP[dep]}")
            return conf.PACKAGE_MAP[dep]

        # 2. apt-cache search:
        search_names = [
            dep,
            dep.lower(),
            dep.replace("-", ""),
            dep.replace("-", "_"),
            dep.replace("_", "-"),
        ]
        for name in search_names:
            result = subprocess.run(["apt-cache", "search", name],
                                    capture_output=True, text=True, check=False)
            lines = result.stdout.splitlines()
            dev_packages = [line.split(" - ")[0] for line in lines if line.startswith("lib") and line.endswith("-dev")]
            if dev_packages:
                logging.info(f"apt-cache found: {dep} -> {dev_packages[0]}")
                return dev_packages[0]

        # 3. pkg-config:
        try:
            result = subprocess.run(["pkg-config", "--list-all"],
                                    capture_output=True, text=True, check=False)
            if dep.lower() in result.stdout.lower():
                # Find which package provides the .pc file
                result2 = subprocess.run(["apt-file", "search", f"{dep}.pc"],
                                         capture_output=True, text=True, check=False)
                if result2.stdout:
                    pkg = result2.stdout.split(":")[0]
                    logging.info(f"pkg-config found: {dep} -> {pkg}")
                    return pkg
        except FileNotFoundError:
            logging.debug("pkg-config not installed, skipping.")

        logging.warning(f"No mapping found for {dep}.")
        return ""

    def _is_package_installed(self, package: str) -> bool:
        try:
            result = subprocess.run(["dpkg", "-s", package],
                                    capture_output=True, text=True, check=False)
            return result.returncode == 0
        except Exception as e:
            logging.error(f"Error checking if {package} is installed: {e}")
            return False

    def _install_package(self, package: str) -> None:
        try:
            subprocess.run(["apt", "install", "-y", package], check=True)
            logging.info(f"{package} installed successfully.")
            if "libgtest-dev" == package:
                subprocess.run(["cmake", ".", "-B", "build_gtest"], cwd="/usr/src/gtest")
                subprocess.run(["make"], cwd="/usr/src/gtest/build_gtest")
                subprocess.run(["cp", "*.a", "/usr/lib/"], cwd="/usr/src/gtest/build_gtest")
        except subprocess.CalledProcessError:
            logging.error(f"Failed to install {package}.", exc_info=True)
        except PermissionError:
            logging.error("Permission denied. Run as root.")

