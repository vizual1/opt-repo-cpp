import os, re, subprocess

def find_cmake_files(test_path: str) -> list[str]:
    cmake_files = []
    for root, dirs, files in os.walk(test_path):
        for file in files:
            if file == "CMakeLists.txt" or file.endswith(".cmake"):
                cmake_files.append(os.path.join(root, file))
    return cmake_files

def find_apt_package_for_cmake(dep_name):
    """
    Given a CMake dependency name, try to find a corresponding apt package dynamically.
    """
    try:
        result = subprocess.run(['pkg-config', '--exists', dep_name],
                                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            cflags = subprocess.run(['pkg-config', '--cflags', dep_name],
                                    capture_output=True, text=True).stdout.strip()
            include_dirs = re.findall(r'-I([^\s]+)', cflags)
            if include_dirs:
                likely_pkg = include_dirs[-1].split('/')[-1]
                return f'lib{likely_pkg}-dev'
            return dep_name.lower() + '-dev'
    except FileNotFoundError:
        pass

    try:
        result = subprocess.run(['apt-cache', 'search', dep_name],
                                capture_output=True, text=True, check=False)
        lines = result.stdout.splitlines()
        dev_packages = [line.split(' - ')[0] for line in lines if 'dev' in line]
        if dev_packages:
            return dev_packages[0]
    except FileNotFoundError:
        pass

    return None

def extract_cmake_packages(cmake_path: str) -> set[str]:
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
