import subprocess, logging
from pathlib import Path
from src.utils.cmake_parser import *

def packages_installer(packages: list[str]) -> list[str]:
    result_packages = []
    for p in packages:
        if not is_package_installed(p):
            logging.info(f"Trying to install package {p}...")
            install_package(p)
        else:
            logging.info(f"Package {p} is already installed.")

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

def cmake_configure(source_path: str, build_path: str, build_type: str = "Release", flags: list[str] = []):
    cmd = ['cmake', '-S', source_path, '-B', build_path, f'-DCMAKE_BUILD_TYPE={build_type}']
    for flag in flags:
        cmd.append(f'-D{flag}=ON')
    try:
        logging.info(f"Run cmd: {cmd}")
        subprocess.run(cmd, check=True)
        logging.info(f"CMake configured {build_path} successfully.")
    except subprocess.CalledProcessError:
        logging.error(f"CMake configuration failed for {build_path}.")

def cmake_build(build_path: str, jobs: int = 0):
    test_dir = Path(build_path)
    cmd = ['cmake', '--build', build_path]
    if jobs > 0:
        cmd += ['-j', str(jobs)]
    try:
        logging.info(f"Run cmd: {cmd}")
        subprocess.run(cmd, check=True)
        logging.info(f"CMake build completed for {build_path}.")
    except subprocess.CalledProcessError:
        logging.error(f"CMake build failed for {build_path}.")

def cmake_test(build_path: str):
    test_dir = Path(build_path)
    cmd = ['ctest', '--output-on-failure']
    try:
        logging.info(f"Run cmd: {cmd} in {test_dir}")
        result = subprocess.run(cmd, cwd=test_dir, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        logging.info(f"CMake tests passed for {build_path}")
        logging.info(result.stdout)
    except subprocess.CalledProcessError as e:
        logging.error(f"CMake tests failed for {build_path}")
        logging.info(e.stdout)

