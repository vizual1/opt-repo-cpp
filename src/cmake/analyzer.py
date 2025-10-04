import logging
from src.cmake.parser import CMakeParser

class CMakeAnalyzer:
    """High-level interface for analyzing CMake repositories."""
    def __init__(self, root: str):
        self.root = root
        self.parser = CMakeParser(self.root)
        self.cmakelists = self.parser.find_files(search="CMakeLists.txt")
        logging.info(f"CMakeLists.txt: {self.cmakelists}")

    def has_root_cmake(self) -> bool:
        return self.parser.has_root_cmake()

    # TODO: test this
    def has_testing(self) -> bool:
        return (self.parser.find_enable_testing(self.cmakelists) and 
                self.parser.can_list_tests(self.cmakelists) and 
                (self.parser.find_add_tests(self.cmakelists) or 
                 self.parser.find_discover_tests(self.cmakelists)))

    def has_build_testing_flag(self) -> dict[str, dict[str, str]]:
        return self.parser.find_test_flags(self.cmakelists)
    
    def has_package_manager(self) -> dict[str, list[str]]:
        return self.parser.check_external_package_manager(self.cmakelists)
    
    def get_testfile(self) -> list[str]:
        return self.parser.find_files(search="CTestTestfile.cmake")
    
    def get_ctest_flags(self) -> set[str]:
        return self.parser.parse_ctest_flags(self.cmakelists)

    def get_enable_testing_flags(self) -> set[str]:
        return self.parser.find_testing_flags(self.root)

    def get_dependencies(self) -> set[str]:
        deps = set()
        for cf in self.cmakelists:
            deps |= self.parser.get_cmake_packages(cf)
        return deps
