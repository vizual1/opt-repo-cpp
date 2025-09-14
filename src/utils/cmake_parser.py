import os, re, logging
from collections import deque
from pathlib import Path

def find_files(test_path: str, search: str) -> list[str]:
    found_files: list[str] = []
    for root, _, files in os.walk(test_path):
        for file in files:
            if file == search:
                found_files.append(os.path.join(root, file))
    return found_files

# TODO: fix checks and parsers below, currently all over the place
def check_ctest_defined(cmake_files: list[str]) -> bool:
    """Checks if include(CTest) is defined in CMake."""
    ctest_pattern = re.compile(r'include\s*\(\s*CTest\s*\)', re.IGNORECASE)

    for cf in cmake_files:
        with open(cf, 'r', errors='ignore') as file:
            content = file.read()
        if ctest_pattern.search(content):
            logging.info(f"CMakeFiles with CTest in {cf}.")
            return True
    return False

def check_enable_testing_defined(cmake_files: list[str]) -> bool:
    """Checks if enable_testing() is defined in CMake."""
    enable_testing_pattern = re.compile(r'enable_testing\s*\(\s*\)', re.IGNORECASE)

    for cf in cmake_files:
        with open(cf, 'r', errors='ignore') as file:
            content = file.read()
        if enable_testing_pattern.search(content):
            logging.info(f"CMakeFiles with enable_testing in {cf}.")
            return True
    return False

# TODO: need better flag parser => parse entire boolean expressions OR, AND, NOT, etc.
def parse_ctest_flags(cmake_files: list[str]) -> set[str]:
    """Parses a CMake file and returns flags needed for CTest."""
    if_pattern = re.compile(r'^\s*if\s*\(\s*(.+?)\s*\)\s*', re.IGNORECASE)
    elseif_pattern = re.compile(r'^\s*elseif\s*\(\s*(.+?)\s*\)\s*', re.IGNORECASE)
    else_pattern = re.compile(r'^\s*else\s*\(\s*\)\s*', re.IGNORECASE)
    endif_pattern = re.compile(r'^\s*endif\s*\(\s*(.*?)\s*\)\s*', re.IGNORECASE)
    #ctest_pattern = re.compile(r'include\s*\(\s*CTest\s*\)|enable_testing\s*\(\s*\)', re.IGNORECASE)
    ctest_pattern = re.compile(r'enable_testing\s*\(\s*\)', re.IGNORECASE)

    condition_stack = deque()
    required_flags = set()

    for cf in cmake_files:
        with open(cf, 'r', errors='ignore') as f:
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
                        required_flags.update(vars_in_cond)

    return required_flags

def get_cmake_packages(cmake_path: str) -> set[str]:
    """Find CMake dependency names from CMake files."""
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

    for match in find_package_pattern.findall(content):
        pkg_name = match[0]
        options = match[2].strip().split() if match[2] else []
        components = []
        if 'COMPONENTS' in options:
            comp_index = options.index('COMPONENTS')
            components = options[comp_index + 1:] 
        packages.add(pkg_name)
        packages.update(components)

    for match in pkg_check_pattern.findall(content):
        modules = match[3].split()
        packages.update(modules)

    return packages

def find_enable_testing_files(test_path: str) -> list[Path]:
    testing_files: list[Path] = []
    enable_testing_pattern = re.compile(r'enable_testing\s*\(\s*\)', re.IGNORECASE)
    for cmake_file in Path(test_path).rglob("CMakeLists.txt"):
        with open(cmake_file, "r", errors="ignore") as f:
            if enable_testing_pattern.search(f.read()):
                testing_files.append(cmake_file)
    return testing_files

def get_add_subdirectory_guards(cmake_file: Path, sub_path: str):
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

def find_testing_flags(test_path: str) -> set[str]:
    testing_files = find_enable_testing_files(test_path)
    all_flags = set()
    for test_file in testing_files:
        current = test_file.parent
        sub_path = test_file.parent.name
        while True:
            parent_file = current.parent / "CMakeLists.txt"
            if not parent_file.exists() or parent_file == current:
                break
            flags = get_add_subdirectory_guards(parent_file, sub_path)
            all_flags.update(flags)
            sub_path = current.name
            current = current.parent
    return all_flags



