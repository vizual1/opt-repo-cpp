import logging, subprocess, re
from pathlib import Path
from src.cmake.analyzer import CMakeAnalyzer
import src.config as conf
from src.filter.llm.prompt import Prompt
from src.filter.llm.openai import OpenRouterLLM

class CMakePackageHandler:
    def __init__(self, analyzer: CMakeAnalyzer):
        self.analyzer = analyzer
        #self.packages, self.python = self._get_packages()
        self.llm = OpenRouterLLM(conf.llm['model'])

    def get_missing_dependencies(self, stdout: str, stderr: str, cache_path: Path) -> set[str]:
        if not cache_path.exists():
            logging.warning("No CMakeCache.txt found, skipping")
        missing_cache = self._find_cache_missing(cache_path)
        logging.info(f"Missing caches: {missing_cache}")
        missing_pkgconfig = self._find_pkgconfig_missing(stdout, stderr)
        logging.info(f"Missing packages: {missing_pkgconfig}")

        # TODO: too fragile, needs different method
        missing_others: set[str] = set()
        for dep in missing_cache | missing_pkgconfig:
            if "-" in dep:
                missing_others.add(dep.split("-")[0])
            if "+" in dep:
                missing_others.add(dep.split("+")[0])
            if "_" in dep and len(dep.split("_")) > 1:
                missing_others.add(dep.split("_")[0])
            if "_" in dep and len(dep.split("_")) > 2:
                missing_others.add("_".join(dep.split("_")[0:2]))
            if "_" in dep and len(dep.split("_")) > 3:
                missing_others.add("_".join(dep.split("_")[0:-1]))
            # 'avahi-compat-libdns_sd'
        logging.info(f"Missing others: {missing_others}")

        return missing_cache | missing_pkgconfig | missing_others

    def _find_cache_missing(self, cache_path: Path) -> set[str]:
        missing = set()
        with open(cache_path) as f:
            for line in f:
                if m := re.match(r"(\w+_DIR):PATH=(.+-NOTFOUND)", line):
                    missing.add(m.group(1).replace("_DIR", ""))
                elif m := re.match(r"(\w+_FOUND):BOOL=FALSE", line):
                    missing.add(m.group(1).replace("_FOUND", ""))
        return missing
    
    def _find_pkgconfig_missing(self, stdout: str, stderr: str) -> set[str]:
        patterns = [
            r"No package '([a-zA-Z0-9_\-\+\.]+)' found",
            r"Could NOT find ([A-Za-z0-9_\-\+\.]+)",
            r"Could not find a package configuration file provided by \"([^\"]+)\"",
            r"Could not find a configuration file for package \"([^\"]+)\"",
            r"([A-Za-z0-9_\-\+\.]+)\s+package NOT found",
            r"No module named ['\"]([^'\"]+)['\"]",
        ]
        missing = set()
        for pattern in patterns:
            missing.update(re.findall(pattern, stdout))
            missing.update(re.findall(pattern, stderr))
        return missing
        #missing = set(re.findall(r"No package '([a-zA-Z0-9_\-\+\.]+)' found", stdout))
        'Could NOT find DBus (missing: DBUS_INCLUDE_DIRS DBUS_LIBRARIES)'
        'CMake 3.24 or higher is required.  You are running version 3.22.1'
        "ModuleNotFoundError: No module named 'menuconfig'"
        'Could not find a package configuration file provided by "Eigen3" with any of the following names"'
        'Could not find a configuration file for package "Qt6" that is compatible with requested version "6.4".'
        'fastcdr package NOT found'

    def llm_prompt(self, errors, missing_cache, missing_pkgconfig) -> str:
        p = Prompt([Prompt.Message(
            role="user",
            content=
                f"You are an expert C++/CMake/Dependency assistant.\nCMake configuration failed with these errors:\n"
                +f"{errors}"
                +f"Missing CMake cache entries: {missing_cache}"
                +f"Missing pkg-config packages: {missing_pkgconfig}"
                +"Please ONLY output shell commands that would install the missing dependencies."
                +"Do NOT provide explanations, text, or comments -> ONLY valid shell commands."
                +"Commands should work on Linux with vcpkg or apt-get where appropriate."
        )])
        out = self.llm.generate(p)
        return out
        
    '''
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

    '''