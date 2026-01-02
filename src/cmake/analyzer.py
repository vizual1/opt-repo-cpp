from src.cmake.parser import CMakeParser
from src.config.constants import DOCKER_IMAGE_MAP
from pathlib import Path

class CMakeAnalyzer:
    """High-level interface for analyzing and parsing CMakeLists.txt files."""
    def __init__(self, repo_path: Path):
        self.root = repo_path
        self.parser = CMakeParser(self.root)

    def reset(self) -> None:
        self.root = self.root
        self.parser = CMakeParser(self.root)

    def has_root_cmake(self) -> bool:
        return self.parser.has_root_cmake()

    def has_testing(self, nolist: bool = False) -> bool:
        list_tests: bool = self.parser.can_list_tests()
        return (self.parser.find_enable_testing() and (nolist or list_tests) and 
               (self.parser.find_add_tests() or self.parser.find_discover_tests()))
    
    def get_list_test_arg(self) -> list[tuple[str, str]]:
        return list(self.parser.list_test_arg)

    def extract_build_testing_flag(self) -> dict[str, dict[str, str]]:
        return self.parser.find_cmake_test_flags()
    
    def get_enable_testing_path(self) -> list[Path]:
        return self.parser.enable_testing_path
    
    def parse_ctest_file(self, text: str) -> list[str]:
        return self.parser.parse_ctest_file(text)
    
    def parse_subdirs(self, text: str) -> list[str]:
        return self.parser.parse_cmake_subdirs(text)
    
    def extract_unit_tests(self, text: str, framework: str) -> list[str]:
        return self.parser.extract_unit_tests(text, framework)

    def get_dependencies(self) -> set[str]:
        deps = self.parser.find_dependencies()
        return deps
    
    def get_ubuntu_version(self) -> str:
        return self.parser.get_ubuntu_for_cmake(self.parser.find_cmake_minimum_required())

    def get_docker(self) -> str:
        return DOCKER_IMAGE_MAP[self.get_ubuntu_version()]
