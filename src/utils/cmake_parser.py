import os, re, logging
from collections import deque

def find_cmake_files(test_path: str) -> list[str]:
    """Search all CMakeLists.txt and .cmake files in the directory."""
    cmake_files: list[str] = []
    for root, _, files in os.walk(test_path):
        for file in files:
            if file == "CMakeLists.txt" or file.endswith(".cmake"):
                cmake_files.append(os.path.join(root, file))
    return cmake_files

def check_ctest_defined(cmake_files: list[str]) -> bool:
    """Checks if CTest is defined in CMake."""
    ctest_pattern = re.compile(r'include\s*\(\s*CTest\s*\)', re.IGNORECASE)
    enable_testing_pattern = re.compile(r'enable_testing\s*\(\s*\)', re.IGNORECASE)

    for cf in cmake_files:
        with open(cf, 'r', errors='ignore') as file:
            content = file.read()
        if ctest_pattern.search(content) or enable_testing_pattern.search(content):
            logging.info("Found CTest.")
            return True
    logging.info("No CTest Found.")
    return False

def parse_ctest_flags(cmake_files: list[str]) -> set[str]:
    """Parses a CMake file and returns flags needed for CTest."""
    if_pattern = re.compile(r'^\s*if\s*\(\s*(.+?)\s*\)\s*', re.IGNORECASE)
    elseif_pattern = re.compile(r'^\s*elseif\s*\(\s*(.+?)\s*\)\s*', re.IGNORECASE)
    else_pattern = re.compile(r'^\s*else\s*\(\s*\)\s*', re.IGNORECASE)
    endif_pattern = re.compile(r'^\s*endif\s*\(\s*(.*?)\s*\)\s*', re.IGNORECASE)
    ctest_pattern = re.compile(r'include\s*\(\s*CTest\s*\)|enable_testing\s*\(\s*\)', re.IGNORECASE)
    
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

def extract_cmake_packages(cmake_path: str) -> set[str]:
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

    logging.info(f"Extracted CMake dependency package names: {packages}")

    return packages

    
"""
def check_packages_installed(packages: list[str]) -> list[str]:
    result_packages = []
    for p in packages:
        if not is_package_installed(p):
            install_package(p)

    return result_packages

def is_package_installed(package: str) -> bool:
    try:
        result = subprocess.run(['dpkg', '-l'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return package in result.stdout
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return False

def install_package(package: str):
    try:
        subprocess.run(['apt', 'install', '-y', package], check=True)
        logging.info(f"{package} has been installed.")
    except subprocess.CalledProcessError:
        logging.error(f"Failed to install {package}.")

def cmake_build(test_path: str):
    cmake_files = find_cmake_files(test_path)
    if cmake_files and check_ctest_defined(cmake_files):
        logging.info(f"Build with CMake for {test_path}.")

        flags = parse_ctest_flags(cmake_files)
        
        #cmake_build(cmake_files, flags)
        #def cmake_build(self, cmake_files: list[str], flags: set[str]):

        cdep_names = set()
        for cf in cmake_files:
            cdep = extract_cmake_packages(cf)
            cdep_names = cdep | cdep_names
        
        print(cdep_names)
        packages_needed = set()
        for cdep in cdep_names:
            package = find_apt_package(cdep)
            if package:
                packages_needed.add(package)

        print(packages_needed)
        packages = check_packages_installed(list(packages_needed))
        print(packages)
"""