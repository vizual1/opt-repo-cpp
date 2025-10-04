import os, re, logging
from collections import deque
from pathlib import Path
import src.cmake.patterns as pattern

# TODO: fix checks and parsers below, currently all over the place and clean up
# patterns to parse possible flags
OPTION_PATTERN = re.compile(r'option\s*\(\s*([A-Za-z0-9_]+)\s+"([^"]*)"\s+(ON|OFF)\s*\)', re.IGNORECASE)
SET_CACHE_PATTERN = re.compile(r'set\s*\(\s*([A-Za-z0-9_]+)\s+([^\s\)]+)\s+CACHE\s+([A-Z]+)\s*"([^"]*)"\s*\)', re.IGNORECASE)
IF_TEST_PATTERN = re.compile(r'if\s*\(\s*([A-Za-z0-9_]*TEST[A-Za-z0-9_]*)\s*\)', re.IGNORECASE)

class CMakeParser:
    def __init__(self, root: str):
        self.root = root
        self.enable_testing_path: list[str] = []
        self.add_test_path: list[str] = []
        self.discover_tests_path: list[str] = []
        self.target_link_path: list[str] = []

    def has_root_cmake(self) -> bool:
        return os.path.exists(os.path.join(self.root, "CMakeLists.txt"))

    def find_files(self, search: str) -> list[str]:
        """Search all files 'search' from root."""
        found_files: list[str] = []
        for root, _, files in os.walk(self.root):
            for file in files:
                if file == search:
                    found_files.append(os.path.join(root, file))
        return found_files
    
    def find_enable_testing(self, cmake_files: list[str]) -> bool:
        """
        Checks if enable_testing() is called anywhere in CMakeLists.txt. 
        Either CMakeLists.txt calls enable_testing() directly or it calls enable_testing() via include(CTest).
        """
        for cf in cmake_files:
            with open(cf, 'r', errors='ignore') as file:
                content = file.read()
            if pattern.enable_testing.search(content) or pattern.include_ctest.search(content):  
               self.enable_testing_path.append(cf)
        
        if self.enable_testing_path:
            logging.info(f"CMakeLists.txt with enable_testing(): {self.enable_testing_path}.")
            return True
        
        return False
    
    def find_add_tests(self, cmake_files: list[str]) -> bool:
        for cf in cmake_files:
            with open(cf, 'r', errors='ignore') as file:
                content = file.read()
            if pattern.add_test.search(content):
                self.add_test_path.append(cf)
        
        if self.add_test_path:
            logging.info(f"CMakeLists.txt with add_test(): {self.add_test_path}.")
            return True
        
        return False
    
    def find_discover_tests(self, cmake_files: list[str]) -> bool:
        for cf in cmake_files:
            with open(cf, 'r', errors='ignore') as file:
                content = file.read()
            if pattern.discover_tests.search(content):
                self.discover_tests_path.append(cf)
        
        if self.discover_tests_path:
            logging.info(f"CMakeLists.txt with *_discover_tests(): {self.discover_tests_path}.")
            return True
        
        return False
    
    def can_list_tests(self, cmake_files: list[str]) -> bool:
        for cf in cmake_files:
            with open(cf, 'r', errors='ignore') as file:
                content = file.read()

            if pattern.target_link_libraries.search(content):
                logging.info(f"GoogleTest|Catch|doctest library link found in {cf}.")
                return True

        return False
    
    def check_external_package_manager(self, cmake_files: list[str]) -> dict[str, list[str]]:
        """
        Detects external C++ package managers used in the project by scanning CMakeLists.txt files.
        Returns a dictionary mapping manager name to a list of CMake files where it was found.
        """
        patterns = {
            "Conan": [
                re.compile(r'include\s*\(\s*Conan\.cmake\s*\)', re.IGNORECASE),
                re.compile(r'conan_basic_setup\s*\(', re.IGNORECASE),
                re.compile(r'conan_cmake_run\s*\(', re.IGNORECASE)
            ],
            "vcpkg": [
                re.compile(r'set\s*\(\s*CMAKE_TOOLCHAIN_FILE.*vcpkg\.cmake\s*\)', re.IGNORECASE),
            ],
            "Hunter": [
                re.compile(r'include\s*\(\s*HunterGate\.cmake\s*\)', re.IGNORECASE),
                re.compile(r'hunter_add_package\s*\(', re.IGNORECASE)
            ],
            "FetchContent": [
                re.compile(r'include\s*\(\s*FetchContent\s*\)', re.IGNORECASE),
                re.compile(r'FetchContent_Declare\s*\(', re.IGNORECASE),
                re.compile(r'FetchContent_MakeAvailable\s*\(', re.IGNORECASE)
            ],
            "ExternalProject": [
                re.compile(r'include\s*\(\s*ExternalProject\s*\)', re.IGNORECASE),
                re.compile(r'ExternalProject_Add\s*\(', re.IGNORECASE)
            ],
            "CPM": [
                re.compile(r'include\s*\(\s*CPM\.cmake\s*\)', re.IGNORECASE),
                re.compile(r'CPMAddPackage\s*\(', re.IGNORECASE)
            ]
        }

        found_managers = {k: [] for k in patterns}

        for cf in cmake_files:
            with open(cf, 'r', errors='ignore') as file:
                content = file.read()
            for manager, pats in patterns.items():
                if any(p.search(content) for p in pats):
                    found_managers[manager].append(cf)

        found_managers = {k: v for k, v in found_managers.items() if v}
        for mgr, files in found_managers.items():
            logging.info(f"Detected package manager {mgr} in {files}")
        return found_managers
    
    def find_test_flags(self, cmake_files: list[str]) -> dict[str, dict[str, str]]:
        test_flags = {}

        for cf in cmake_files:
            with open(cf, "r", errors="ignore") as f:
                content = f.read()

            if pattern.include_ctest.search(content):
                if "BUILD_TESTING" not in test_flags:
                    test_flags["BUILD_TESTING"] = {
                        "description": "Enable CTest-based testing",
                        "default": "ON"
                    }

            for match in OPTION_PATTERN.finditer(content):
                name, desc, default = match.groups()
                if "TEST" in name.upper():
                    test_flags[name] = {"type": "BOOL", "description": desc.strip(), "default": default}

            for match in SET_CACHE_PATTERN.finditer(content):
                name, value, vartype, desc = match.groups()
                if "TEST" in name.upper():
                    test_flags[name] = {"type": vartype.upper(), "description": desc.strip(), "default": value}

            for match in IF_TEST_PATTERN.finditer(content):
                var = match.group(1)
                if var not in test_flags:
                    test_flags[var] = {
                        "type": "BOOL",
                        "description": f"Implicit test flag used in {cf}",
                        "default": "undefined"
                    }

        logging.info("Discovered test flags:")
        for k, v in test_flags.items():
            logging.info(f"  - {k} (default={v['default']}): {v['description']}")

        return test_flags


    def parse_ctest_flags(self, cmake_files: list[str]) -> set[str]:
        """Parses a CMake file and returns flags needed for ctest."""
        required_conditions: set[str] = set()

        for cf in cmake_files:
            required_conditions |= self.parse_flag(cf)

        return required_conditions
        
    def parse_flag(self, cmake_file: str) -> set:
        if_pattern = re.compile(r'^\s*if\s*\(\s*(.+?)\s*\)\s*', re.IGNORECASE)
        elseif_pattern = re.compile(r'^\s*elseif\s*\(\s*(.+?)\s*\)\s*', re.IGNORECASE)
        else_pattern = re.compile(r'^\s*else\s*\(\s*\)\s*', re.IGNORECASE)
        endif_pattern = re.compile(r'^\s*endif\s*\(\s*(.*?)\s*\)\s*', re.IGNORECASE)
        ctest_pattern = re.compile(r'enable_testing\s*\(\s*\)|add_test\s*\(', re.IGNORECASE)

        condition_stack = deque()
        required_flags = set()

        with open(cmake_file, 'r', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if m := if_pattern.match(line):
                    condition_stack.append(m.group(1))
                elif m := elseif_pattern.match(line):
                    if condition_stack:
                        condition_stack.pop()
                        condition_stack.append(m.group(1))
                elif else_pattern.match(line):
                    if condition_stack:
                        condition_stack.pop()
                        condition_stack.append("ELSE")
                elif endif_pattern.match(line):
                    if condition_stack:
                        condition_stack.pop()

                if ctest_pattern.search(line):
                    for cond in condition_stack:
                        vars_in_cond = re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\b', cond)
                        logging.info(f"COND: {vars_in_cond}")
                        required_flags.update(vars_in_cond)
        
        return required_flags


    def find_enable_testing_files(self, test_path: str) -> list[Path]:
        testing_files: list[Path] = []
        enable_testing_pattern = re.compile(r'enable_testing\s*\(\s*\)', re.IGNORECASE)
        for cmake_file in Path(test_path).rglob("CMakeLists.txt"):
            with open(cmake_file, "r", errors="ignore") as f:
                if enable_testing_pattern.search(f.read()):
                    testing_files.append(cmake_file)
        return testing_files

    def get_add_subdirectory_guards(self, cmake_file: Path, sub_path: str):
        """Return list of flags in if() that guard the add_subdirectory(sub_path)"""
        pattern = re.compile(r"add_subdirectory\s*\(\s*{}\s*\)".format(re.escape(sub_path)))
        if_pattern = re.compile(r'^\s*if\s*\(\s*(.+?)\s*\)', re.IGNORECASE)

        stack = []
        flags = set()
        with open(cmake_file, "r", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if m := if_pattern.match(line):
                    stack.append(m.group(1))
                elif line.startswith("endif"):
                    if stack:
                        stack.pop()
                elif pattern.search(line):
                    for cond in stack:
                        vars_in_cond = re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\b', cond)
                        flags.update(vars_in_cond)
        return flags

    def find_testing_flags(self, test_path: str) -> set[str]:
        testing_files = self.find_enable_testing_files(test_path)
        all_flags = set()
        for test_file in testing_files:
            current = test_file.parent
            sub_path = test_file.parent.name
            while True:
                parent_file = current.parent / "CMakeLists.txt"
                if not parent_file.exists() or parent_file == current:
                    break
                flags = self.get_add_subdirectory_guards(parent_file, sub_path)
                all_flags.update(flags)
                sub_path = current.name
                current = current.parent
        return all_flags

    def get_cmake_packages(self, cmake_path: str) -> set[str]:
        """Find CMake dependency names from CMakeLists.txt."""
        with open(cmake_path, 'r', errors='ignore') as file:
            content = file.read()
        
        find_package_pattern = re.compile(
            r'find_package\(\s*([^\s)]+)'              
            r'(?:\s+([0-9.]+))?'                       
            r'((?:\s+(?:REQUIRED|QUIET|COMPONENTS\s+[^\)]+))*)'
            r'\)', re.IGNORECASE
        )
        
        pkg_check_pattern = re.compile(
            r'pkg_check_modules\(\s*([^\s)]+)'      
            r'((?:\s+(REQUIRED|QUIET))*)'        
            r'\s+([^\)]+)\)',           
            re.IGNORECASE
        )

        packages = set()

        def normalize(name: str) -> str:
            name = re.split(r'[<>= ]', name)[0] # remove version constraints (>=, =, <, etc.)
            name = name.replace("++", "pp") # replace "++" -> "pp"
            name = re.sub(r'[-_]\d+(\.\d+)*$', '', name) # remove trailing version suffixes: Foo-2.5 -> Foo
            name = name.lower() # lowercase everything (CMake is case-insensitive for packages)
            return name

        for match in find_package_pattern.findall(content):
            pkg_name = normalize(match[0])
            options = match[2].strip().split() if match[2] else []
            components = []
            if 'COMPONENTS' in options:
                comp_index = options.index('COMPONENTS')
                components = options[comp_index + 1:] 
            if pkg_name:
                packages.add(pkg_name)
            if components:    
                packages.update(components)

        for match in pkg_check_pattern.findall(content):
            modules = match[3].split()
            for m in modules:
                if m:
                    packages.add(normalize(m))

        logging.debug(f"Normalized package set from {cmake_path}: {packages}")
        return packages


