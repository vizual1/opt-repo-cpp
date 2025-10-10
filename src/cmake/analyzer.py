from src.cmake.parser import CMakeParser

class CMakeAnalyzer:
    """High-level interface for analyzing CMake repositories."""
    def __init__(self, root: str):
        self.root = root
        self.parser = CMakeParser(self.root)

    def has_root_cmake(self) -> bool:
        return self.parser.has_root_cmake()

    def has_testing(self) -> bool:
        return (self.parser.find_enable_testing() and self.parser.can_list_tests() and 
               (self.parser.find_add_tests() or self.parser.find_discover_tests()))
    
    def get_list_test_arg(self) -> list[str]:
        return list(self.parser.list_test_arg)

    def has_build_testing_flag(self) -> dict[str, dict[str, str]]:
        return self.parser.find_test_flags()

    def get_dependencies(self) -> set[str]:
        deps = self.parser.find_dependencies()
        return deps
