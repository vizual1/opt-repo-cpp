import os, logging, re
from cmakeast.printer import ast
from typing import Optional

# TODO: fix checks and parsers below, currently all over the place and clean up
class CMakeParser:
    def __init__(self, root: str):
        self.root = root
        self.enable_testing_path: list[str] = []
        self.add_test_path: list[str] = []
        self.discover_tests_path: list[str] = []
        self.target_link_path: list[str] = []
        self.list_test_arg: set[str] = set()
        self.cmake_files: list[str] = self.find_files(search="CMakeLists.txt")
        self.find_cmake_files: list[str] = self.find_files(pattern=re.compile(r"Find.*\.cmake$", re.IGNORECASE))
        self.cmake_function_calls: list[tuple[ast.FunctionCall, str]] = self._find_all_function_calls(self.cmake_files)

    def has_root_cmake(self) -> bool:
        return os.path.exists(os.path.join(self.root, "CMakeLists.txt"))

    def find_files(self, search: str = "", pattern: Optional[re.Pattern] = None) -> list[str]:
        """Search all files 'search' from root."""
        found_files: list[str] = []
        for root, _, files in os.walk(self.root):
            for file in files: 
                if file == search or (pattern and pattern.match(file)):
                    found_files.append(os.path.join(root, file))
        return found_files
    
    def find_cmake_minimum_required(self) -> str:
        cmake_file: str = os.path.join(self.root, "CMakeLists.txt")
        root_function_calls: list[tuple[ast.FunctionCall, str]] = self._find_all_function_calls([cmake_file]) 
        call, cf = self._find_function_calls(name="cmake_minimum_required", fcalls=root_function_calls)[0]
        arguments: list = call.arguments
        # VERSION x.x..something?
        logging.info(f"CMake minimum veresion required: {arguments}")
        # TODO: read minimum requirement <-> maximum?
        return ""
    
    def find_ctest_exec(self) -> list[str]:
        # TODO: test
        logging.info("Searching for ctest executables...")
        test_files = self.find_files("CTestTestfile.cmake")
        self.ctest_function_calls: list[tuple[ast.FunctionCall, str]] = self._find_all_function_calls(test_files) 
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
            self.enable_testing_path.append(cf)
        if self.enable_testing_path:
            logging.info(f"CMakeLists.txt with enable_testing(): {self.enable_testing_path}.")
            return True
        
        return False
    
    def find_add_tests(self) -> bool:
        logging.info("Search for add_tests...")
        calls = self._find_function_calls(name="add_test")
        for _, cf in calls:
            self.add_test_path.append(cf)
        if self.add_test_path:
            logging.info(f"CMakeLists.txt with add_test(): {self.add_test_path}.")
            return True
        
        return False
    
    def find_discover_tests(self) -> bool:
        logging.info("Search for *_discover_tests...")
        calls = self._find_function_calls(ends="_discover_tests")
        for _, cf in calls:
            self.discover_tests_path.append(cf)
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
        all_calls: list[tuple[ast.FunctionCall, str]] = []
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
        calls: list[tuple[ast.FunctionCall, str]] = []
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
                #for argument in arguments:
                #if hasattr(argument, "contents"):
                arg_name = arguments[0].contents.strip()
                if self._valid_name(arg_name):
                    if "::" in arg_name:
                        packages.add(arg_name.split("::")[0])
                    else:
                        packages.add(arg_name)

        logging.info(f"Found possible dependencies: {packages}")
        return packages


    def _check_cmakeast_class(self, node):
        return hasattr(node, "__class__") and node.__class__.__module__.startswith("cmakeast")

    def _walk_ast(self, node):
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

    def _find_function_calls(self, name: str = "", _args: list[str] = [], starts: str = "", ends: str = "", fcalls: list[tuple[ast.FunctionCall, str]] = []) -> list[tuple[ast.FunctionCall, str]]:
        calls: list[tuple[ast.FunctionCall, str]] = []
        if not fcalls:
            fcalls = self.cmake_function_calls
        for statement, cf in fcalls:
            if (name and statement.name == name) or (ends and statement.name.endswith(ends)) or (starts and statement.name.startswith(starts)):
                arguments: list = statement.arguments
                if not _args:
                    calls.append((statement, cf))
                count = 0
                for argument in arguments:
                    if (hasattr(argument, "contents") and argument.contents.strip() in _args):
                        count += 1
                if count >= len(_args):
                    calls.append((statement, cf))   
        return calls
    
    def _find_all_function_calls(self, files: list[str]) -> list[tuple[ast.FunctionCall, str]]:
        calls: list[tuple[ast.FunctionCall, str]] = []
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