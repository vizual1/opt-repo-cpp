from src.utils.cmake_parser import *
from src.utils.package_resolver import find_apt_package

class CMakeAdapter:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.cmake_files = find_cmake_files(repo_path)

    def has_ctest(self) -> bool:
        return check_ctest_defined(self.cmake_files)

    def get_flags(self) -> set[str]:
        return parse_ctest_flags(self.cmake_files)

    def get_dependencies(self) -> set[str]:
        deps = set()
        for cf in self.cmake_files:
            deps |= extract_cmake_packages(cf)
        return deps
    
    def get_packages(self) -> set[str]:
        deps = self.get_dependencies()
        packages_needed = set([find_apt_package(dep) for dep in deps])
        return packages_needed
    