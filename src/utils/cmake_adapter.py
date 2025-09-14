import logging
from src.utils.cmake_parser import *
from src.utils.package_resolver import find_apt_package

class CMakeAdapter:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.cmake_files = find_files(repo_path, search="CMakeLists.txt")
        logging.info(f"cmake_files: {self.cmake_files}")

    def has_ctest(self) -> bool:
        return check_ctest_defined(self.cmake_files)
    
    def has_enable_testing(self) -> bool:
        return check_enable_testing_defined(self.cmake_files)
    
    def get_testfile(self) -> list[str]:
        return find_files(self.repo_path, search="CTestTestfile.cmake")
    
    def get_ctest_flags(self) -> set[str]:
        return parse_ctest_flags(self.cmake_files)

    def get_enable_testing_flags(self) -> set[str]:
        return find_testing_flags(self.repo_path)

    def get_dependencies(self) -> set[str]:
        deps = set()
        for cf in self.cmake_files:
            deps |= get_cmake_packages(cf)
        return deps
    
    def get_packages(self) -> set[str]:
        deps = self.get_dependencies()
        packages_needed = set()
        for dep in deps:
            # TODO: add cache load if exist otherwise find_apt_package and save
            pkg = find_apt_package(dep)
            if pkg:
                packages_needed.add(pkg)
        return packages_needed
    