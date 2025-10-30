import os, logging, re
from cmakeast.printer import ast
from typing import Optional, Generator, Union
from pathlib import Path

class CMakeParser:
    def __init__(self, root: Path):
        self.root = root

        self.enable_testing_path: list[Path] = []
        self.add_test_path: list[Path] = []
        self.discover_tests_path: list[Path] = []
        self.target_link_path: list[Path] = []
        self.list_test_arg: set[str] = set()

        self._cmake_files: Optional[list[Path]] = None #self.find_files(search="CMakeLists.txt")
        #self.find_cmake_files: list[Path] = self.find_files(pattern=re.compile(r"Find.*\.cmake$", re.IGNORECASE))
        self._cmake_function_calls: Optional[list[tuple[ast.FunctionCall, Path]]] = None # self._find_all_function_calls(self.cmake_files)

    @property
    def cmake_files(self) -> list[Path]:
        if self._cmake_files is None:
            self._cmake_files = self.find_files(search="CMakeLists.txt")
        return self._cmake_files

    @property
    def cmake_function_calls(self) -> list[tuple[ast.FunctionCall, Path]]:
        if self._cmake_function_calls is None:
            self._cmake_function_calls = self._find_all_function_calls(self.cmake_files)
        return self._cmake_function_calls

    def has_root_cmake(self) -> bool:
        return (self.root / "CMakeLists.txt").exists()

    def find_files(self, search: str = "", pattern: Optional[re.Pattern] = None) -> list[Path]:
        """Search all files 'search' from root."""
        found_files: list[Path] = []
        for root, _, files in os.walk(self.root):
            for file in files: 
                if file == search or (pattern and pattern.match(file)):
                    found_files.append(Path(root, file))
        return found_files
    
    def find_cmake_minimum_required(self) -> str:
        cmake_file: Path = Path(self.root, "CMakeLists.txt")
        root_function_calls: list[tuple[ast.FunctionCall, Path]] = self._find_all_function_calls([cmake_file]) 
        cmake_minimum_calls, cf = self._find_function_calls(name="cmake_minimum_required", fcalls=root_function_calls)[0]
        
        if not cmake_minimum_calls:
            logging.warning("No cmake_minimum_required found, using default 3.16")
            return "3.16"
        
        arguments: list = cmake_minimum_calls.arguments

        for arg in arguments:
            arg_str = str(arg)
            #version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', arg_str)
            version_match = re.search(r'(\d+\.\d+(?:\.\d+)*)', arg_str)
            if version_match:
                logging.info(f"cmake_minimum_required found: {version_match}")
                return version_match.group(1)
        
        logging.warning("No cmake_minimum_required found, using default 3.16")
        return "3.16"
    
    def find_ctest_exec(self) -> list[str]:
        logging.info("Searching for ctest executables...")
        test_files = self.find_files("CTestTestfile.cmake")
        self.ctest_function_calls: list[tuple[ast.FunctionCall, Path]] = self._find_all_function_calls(test_files) 
        all_exec: list[str] = []
        calls = self._find_function_calls(name="add_test", fcalls=self.ctest_function_calls)
        for call, tf in calls:
            arguments: list = call.arguments
            if len(arguments) == 2:
                name = arguments[0].contents if hasattr(arguments[0], "contents") else ""
                exec = arguments[1].contents if hasattr(arguments[1], "contents") else ""
                if exec:
                    all_exec.append(exec)
        logging.info("Found ctest executables:")
        for exec in all_exec:
            logging.info(f"  -./{exec}")
        return all_exec
    
    def find_enable_testing(self) -> bool:
        """
        Checks if enable_testing() is called anywhere in CMakeLists.txt. 
        Either CMakeLists.txt calls enable_testing() directly or it calls enable_testing() via include(CTest).
        """
        logging.info("Searching for enable_testing()...")
        calls = self._find_function_calls(name="enable_testing")
        calls += self._find_function_calls(name="include", _args=["CTest"])
        for _, cf in calls:
            self.enable_testing_path.append(Path(cf))
        if self.enable_testing_path:
            logging.info(f"CMakeLists.txt with enable_testing(): {self.enable_testing_path}.")
            return True
        
        return False
    
    def find_add_tests(self) -> bool:
        logging.info("Search for add_tests...")
        calls = self._find_function_calls(name="add_test")
        for _, cf in calls:
            self.add_test_path.append(Path(cf))
        if self.add_test_path:
            logging.info(f"CMakeLists.txt with add_test(): {self.add_test_path}.")
            return True
        
        return False
    
    def find_discover_tests(self) -> bool:
        logging.info("Search for *_discover_tests...")
        calls = self._find_function_calls(ends="_discover_tests")
        for _, cf in calls:
            self.discover_tests_path.append(Path(cf))
        if self.discover_tests_path:
            logging.info(f"CMakeLists.txt with *_discover_tests(): {self.discover_tests_path}.")
            return True
        
        return False
    
    def can_list_tests(self) -> bool:
        libraries: list[str] = [
            "GTest::gtest", "GTest::gtest_main", "GTest::gmock", "GTest::gmock_main", 
            "gtest", "gtest_main", "gmock", "gmock_main",
            "Catch2::Catch2", "Catch::Main",
            "Catch2::Catch2WithMain", "Catch2::Catch2WithMainNoExit", "Catch2::Catch2WithRunner"
            "doctest", "doctest::doctest", "doctest::doctest_main",
            "Boost::unit_test_framework", "boost_unit_test_framework",
            "Qt::Test", "Qt5::Test", "Qt6::Test"
        ]

        logging.info("Searching for target_link_libraries to isolate test cases...")
        all_calls: list[tuple[ast.FunctionCall, Path]] = []
        for library in libraries:
            calls = self._find_function_calls(name="target_link_libraries", _args=[library])
            for _, cf in calls:
                logging.info(f"target_link_libraries found {library} in {cf}.")
                all_calls += calls
                if "gtest" in library.lower():
                    # run individual tests with ./test_executable --gtest_filter=TESTNAME
                    self.list_test_arg.add("--gtest_list_tests")
                elif "catch" in library.lower():
                    # run individual tests with ./test_executable TESTNAME
                    self.list_test_arg.add("--list-tests") #maybe also --list-test-cases possible
                elif "doctest" in library.lower():
                    # run individual tests with ./test_executable TESTNAME
                    self.list_test_arg.add("--list-test-cases") #maybe also --list-test-suites possible
                elif "boost" in library.lower():
                    # run individual tests wiht ./test_executable --run_test=suite/test
                    self.list_test_arg.add("--list_content")
                elif "qt" in library.lower():
                    # run individual tests wiht ./test_executable TESTNAME
                    self.list_test_arg.add("-functions")

        if all_calls:
            logging.info(f"target_link_libraries(...) to isolate test cases found.")
            return True

        return False
    
    def find_test_flags(self) -> dict[str, dict[str, str]]:
        test_flags = {}

        logging.info("Searching for possible test flags...")
        if "BUILD_TESTING" not in test_flags and self._find_function_calls(name="include", _args=["CTest"]):
            test_flags["BUILD_TESTING"] = {
                "desc": "Enable CTest-based testing",
                "default": "ON"
            }

        options = self._find_function_calls(name="option")
        for option, cf in options:
            arguments: list = option.arguments
            if len(arguments) == 0:
                continue
            arg_name = arguments[0].contents.strip() if hasattr(arguments[0], "contents") else None
            if arg_name and self._valid_name(arg_name) and "TEST" in arg_name.upper():
                desc = arguments[1].contents.strip() if len(arguments) > 1 and hasattr(arguments[1], "contents") else "option"
                default = arguments[2].contents.strip() if len(arguments) > 2 and hasattr(arguments[2], "contents") else ""
                test_flags[arg_name] = {"type": "BOOL", "desc": desc, "default": default}

        set_caches = self._find_function_calls(name="set")
        for set_cache, cf in set_caches:
            arguments: list = set_cache.arguments
            if len(arguments) == 0:
                continue
            exist_cache = any(hasattr(argument, "contents") and argument.contents == "CACHE" for argument in arguments)
            if exist_cache:
                arg_name = arguments[0].contents if hasattr(arguments[0], "contents") else None
                if arg_name and self._valid_name(arg_name) and "TEST" in arg_name.upper():
                    default = arguments[1].contents.strip() if len(arguments) > 1 and hasattr(arguments[1], "contents") else ""
                    test_flags[arg_name] = {"default": default, "desc": "cache"}

        branches = self._find_function_calls(name="if")
        branches += self._find_function_calls(name="elseif")
        for branch, cf in branches:
            arguments: list = branch.arguments
            for argument in arguments:
                arg_name = argument.contents if hasattr(argument, "contents") else None
                if arg_name and self._valid_name(arg_name) and "TEST" in arg_name.upper():
                    test_flags[arg_name] = {"type": "BOOL", "desc": f"Implicit test flag used in {cf}", "default": "undefined"}

        logging.info("Discovered test flags:")
        for k, v in test_flags.items():
            logging.info(f"  - {k} (default={v['default']}): {v['desc']}")

        return test_flags

    def find_unit_tests(self, text: str) -> list[str]:
        # TODO: extract the list tests to unit tests
        return []

    def find_dependencies(self) -> set[str]:
        """Find CMake dependency names from CMakeLists.txt."""
        logging.info("Searching for possible dependencies...")
        calls: list[tuple[ast.FunctionCall, Path]] = []
        calls += self._find_function_calls(name="include", starts="Find")
        calls += self._find_function_calls(name="find_package")
        calls += self._find_function_calls(name="pkg_check_modules")
        #calls += self._find_function_calls(name="target_link_libraries")
        #calls += self._find_function_calls(name="include_directories")
        #calls += self._find_function_calls(name="target_include_directories")
        #calls += self._find_function_calls(name="add_subdirectory")
            
        packages: set[str] = set()
        for call, _ in calls:
            arguments = call.arguments
            if arguments and hasattr(arguments[0], "contents"):
                arg_name = arguments[0].contents.strip()
                if self._valid_name(arg_name):
                    if "::" in arg_name:
                        packages.add(arg_name.split("::")[0])
                    else:
                        packages.add(arg_name)

        logging.info(f"Found possible dependencies: {packages}")
        return packages

    def _check_cmakeast_class(self, node) -> bool:
        return hasattr(node, "__class__") and node.__class__.__module__.startswith("cmakeast")

    def _walk_ast(self, node) -> Generator[ast.FunctionCall, None, None]:
        if isinstance(node, list):
            for item in node:
                yield from self._walk_ast(item)
        elif self._check_cmakeast_class(node):
            yield node
            for attr_name in dir(node):
                if attr_name.startswith("_"):
                    continue
                try:
                    value = getattr(node, attr_name)
                    if isinstance(value, (list,)) or self._check_cmakeast_class(value):
                        yield from self._walk_ast(value)
                except Exception:
                    continue

    def _find_function_calls(self, name: str = "", _args: list[str] = [], starts: str = "", ends: str = "", fcalls: list[tuple[ast.FunctionCall, Path]] = []) -> list[tuple[ast.FunctionCall, Path]]:
        calls: list[tuple[ast.FunctionCall, Path]] = []
        if not fcalls:
            fcalls = self.cmake_function_calls
        for statement, cf in fcalls:
            if (name and statement.name == name) or (ends and statement.name.endswith(ends)) or (starts and statement.name.startswith(starts)):
                arguments: list = statement.arguments
                if not _args:
                    calls.append((statement, Path(cf)))
                count = 0
                for argument in arguments:
                    if (hasattr(argument, "contents") and argument.contents.strip() in _args):
                        count += 1
                if count >= len(_args):
                    calls.append((statement, Path(cf)))   
        return calls
    
    def _find_all_function_calls(self, files: list[Path]) -> list[tuple[ast.FunctionCall, Path]]:
        calls: list[tuple[ast.FunctionCall, Path]] = []
        for cf in files:
            with open(cf, 'r', errors='ignore') as file:
                content = file.read()
            try:
                statements = ast.parse(content).statements
            except Exception as e:
                logging.warning(f"{cf} has an error: {e}")
                continue
            cmake_statements = self._walk_ast(statements)
            for statement in cmake_statements:
                if isinstance(statement, ast.FunctionCall):
                    calls.append((statement, cf))
        return calls
    
    def _valid_name(self, name: str) -> bool:
        keywords = {
            "REQUIRED", "OPTIONAL", "QUIET", "EXACT", "CONFIG", "NO_MODULE", "PRIVATE", 
            "PUBLIC", "INTERFACE", "BEFORE", "IMPORTED_TARGET", "REGEX", "INCLUDE", "PATH",
            "COMPONENTS"
        }
        if name.upper() in keywords:
            return False
        if "/" in name or "\\" in name or name.startswith("."):
            return False # relative/absolute paths
        if "{" in name or "}" in name:
            return False # variables
        if "\"" in name or "'" in name:
            return False # string
        if re.match(r'^\d+(\.\d+)*$', name):
            return False # version numbers
        if name.endswith(('.so', '.a', '.lib', '.dll', '.dylib', '.cmake', '.txt', '.h', '.cc', '.cpp')):
            return False # files
        if name.startswith(('test_', 'example_', 'demo_', 'benchmark_')):
            return False # internal variables
        if not name or len(name) < 2:
            return False # single letter
        if "<" in name or ">" in name:
            return False
        return True
    
    def get_ubuntu_for_cmake(self, cmake_version: str) -> str:
        version_num = self._version_to_number(cmake_version)

        """
        if version_num >= 328:
            return "ubuntu:24.04"
        elif version_num >= 322:
            return "ubuntu:22.04" 
        elif version_num >= 316:
            return "ubuntu:20.04"
        elif version_num >= 310:
            return "ubuntu:18.04"
        else:
            return "ubuntu:22.04" 
        """
        if version_num <= 305:
            return "ubuntu:16.04"
        elif version_num <= 310:
            return "ubuntu:18.04"
        elif version_num <= 316:
            return "ubuntu:20.04"
        elif version_num <= 322:
            return "ubuntu:22.04"
        else:
            return "ubuntu:24.04"

    def _version_to_number(self, version_str: str) -> int:
        """
        Parses a cmake_minimum_required(VERSION ...) line and returns a numeric version (major*100 + minor).
        If a range is given, takes the maximum version in the range.
        If only a single version is given, picks the latest version known to be backward-compatible with it.
        """
        COMPATIBILITY_MAP = {
            208: 300, 305: 322, 310: 327, 316: 327
        }
        LATEST_KNOWN = 327

        try:
            clean_version = re.sub(r'[^\d.\s.]', '', version_str)

            if '...' in version_str:
                versions = [v.strip() for v in clean_version.split('...') if v.strip()]
                if len(versions) >= 2:
                    parts1 = [int(x) for x in versions[0].split('.')]
                    parts2 = [int(x) for x in versions[1].split('.')]
                    version_to_use = versions[0] if parts1 > parts2 else versions[1]
                else:
                    return LATEST_KNOWN
            else:
                parts = clean_version.strip().split('.')
                major = int(parts[0]) if len(parts) > 0 else 0
                minor = int(parts[1]) if len(parts) > 1 else 0
                min_version_num = major * 100 + minor

                for lower_bound, upper_bound in sorted(COMPATIBILITY_MAP.items()):
                    if min_version_num <= lower_bound:
                        return upper_bound
                return LATEST_KNOWN
            
            parts = version_to_use.split('.')
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0

            return major * 100 + minor

        except (ValueError, IndexError):
            return LATEST_KNOWN


    def parse_ctest_output(self, output: str) -> dict[str, Union[int, float]]:
        """Parse CTest output text to extract key test statistics."""
        stats: dict[str, Union[int, float]] = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "total_time_sec": 0.0,
            "pass_rate": 0,
        }

        m = re.search(r"(\d+)% tests passed,\s*(\d+)\s*tests failed out of\s*(\d+)", output)
        if m:
            pass_rate, failed, total = map(int, m.groups())
            passed = total - failed
            stats.update({
                "passed": passed,
                "failed": failed,
                "total": total,
                "pass_rate": pass_rate
            })

        m = re.search(r"(\d+)\s*tests skipped", output)
        if m:
            stats["skipped"] = int(m.group(1))

        m = re.search(r"Total Test time \(real\)\s*=\s*([\d\.]+)\s*sec", output)
        if m:
            stats["total_time_sec"] = float(m.group(1))

        return stats
