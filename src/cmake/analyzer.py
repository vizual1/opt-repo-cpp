from src.cmake.parser import CMakeParser
import src.config as conf
from pathlib import Path
from typing import Union

class CMakeAnalyzer:
    """High-level interface for analyzing CMake repositories."""
    def __init__(self, root: Path):
        self.root = root
        self.parser = CMakeParser(self.root)

    def reset(self) -> None:
        self.root = self.root
        self.parser = CMakeParser(self.root)

    def has_root_cmake(self) -> bool:
        return self.parser.has_root_cmake()

    def has_testing(self, nolist: bool = False) -> bool:
        return (self.parser.find_enable_testing() and (nolist or self.parser.can_list_tests()) and 
               (self.parser.find_add_tests() or self.parser.find_discover_tests()))
    
    def get_list_test_arg(self) -> list[str]:
        return list(self.parser.list_test_arg)

    def has_build_testing_flag(self) -> dict[str, dict[str, str]]:
        return self.parser.find_test_flags()

    def get_dependencies(self) -> set[str]:
        deps = self.parser.find_dependencies()
        return deps
    
    def get_ubuntu_version(self) -> str:
        return self.parser.get_ubuntu_for_cmake(self.parser.find_cmake_minimum_required())

    def get_docker(self) -> str:
        return conf.docker_map[self.get_ubuntu_version()]

    def parse_ctest_output(self, output: str) -> dict[str, Union[int, float]]:
        return self.parser.parse_ctest_output(output)