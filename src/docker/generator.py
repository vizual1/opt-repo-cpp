import logging
import src.config as conf
from src.utils.commit import *
#from src.cmake.adapter import CMakeAdapter
from src.utils.conflict_resolver import *
from src.cmake.process import CMakePackageHandler, CMakeProcess
from src.cmake.analyzer import CMakeAnalyzer

class DockerBuilder:
    def __init__(self, url: str = ""):
        self.storage = conf.storage
        self.repo_ids = get_repo_ids(os.path.join(self.storage['repo_urls']), url)

    def create(self, sha: str = "", ignore_conflict: bool = False):
        for repo in self.repo_ids:
            repo_info = repo.split("/")
            owner = repo_info[0].strip()
            name = repo_info[1].strip()
            folder = f"{owner}_{name}"

            if not sha:
                commits = get_filtered_commits(os.path.join(self.storage['dataset'], f"{folder}_filtered.txt"))
            else:
                commits = get_filtered_commits(os.path.join(self.storage['dataset'], f"{folder}_{sha}.txt"))

            for (current_sha, parent_sha) in commits:
                commit_path = os.path.join(self.storage['dataset'], f"{folder}_{current_sha}")

                # TODO: rather than running the code below, create Dockerfile for each commit
                # TODO: only get CMakeLists.txt rather than entire repo to get necessary packages and flags
                parent_url = f"https://api.github.com/repos/{owner}/{name}/zipball/{parent_sha}"
                parent_path = os.path.join(commit_path, "parent")
                if not os.path.exists(parent_path):
                    get_commit(parent_url, parent_path)
                parent_analyzer = CMakeAnalyzer(parent_path)

                #parent_analyzer = CMakeFlagsAnalyzer(parent_path)
                #testing_flags = parent_analyzer.analyze()
                #logging.info(f"TESTING: {testing_flags}")

                current_url = f"https://api.github.com/repos/{owner}/{name}/zipball/{current_sha}"
                current_path = os.path.join(commit_path, "current")
                if not os.path.exists(current_path):
                    get_commit(current_url, current_path)
                current_analyzer = CMakeAnalyzer(current_path)

                #if parent_adapter.has_ctest() and current_adapter.has_ctest():
                #    logging.info(f"CTest found in commit {parent_sha} and {current_sha}.")
                #    parent_flags = parent_adapter.get_ctest_flags()
                #    current_flags = current_adapter.get_ctest_flags()

                has_testing = parent_analyzer.has_testing() and current_analyzer.has_testing()
                is_cmake_root = parent_analyzer.is_cmake_root() and current_analyzer.is_cmake_root()
                #if parent_adapter.has_enable_testing() and current_analyzer.has_enable_testing():
                if has_testing and is_cmake_root:
                    logging.info(f"CMake at root and CTest found in current and parent commit ({current_sha}).")
                    parent_flags = parent_analyzer.get_enable_testing_flags() | parent_analyzer.get_ctest_flags()
                    current_flags = current_analyzer.get_enable_testing_flags() | current_analyzer.get_ctest_flags()
                
                else:
                    continue
                
                parent_package_handler = CMakePackageHandler(parent_analyzer)
                current_package_handler = CMakePackageHandler(current_analyzer)
                parent_packages = parent_package_handler.packages
                current_packages = current_package_handler.packages

                logging.info(f"Flags parent: {parent_flags}") 
                logging.info(f"Flags current: {current_flags}")
                logging.info(f"Packages parent: {parent_packages}") 
                logging.info(f"Packages current: {current_packages}")
                
                if ignore_conflict:
                    logging.warning("Package conflicts are ignored.")
                
                if ignore_conflict or not check_package_conflict(parent_packages, current_packages):
                    parent_package_handler.packages_installer()
                    current_package_handler.packages_installer()

                    parent_build_path = os.path.join(parent_path, "build")
                    testfile_path = CMakeAnalyzer(parent_build_path).get_testfile()
                    if testfile_path: 
                        test_path = testfile_path[0].removesuffix("CTestTestfile.cmake")
                    else:
                        test_path = parent_build_path
                    CMakeProcess(parent_path, parent_build_path, test_path).run()

                    current_build_path = os.path.join(current_path, "build")
                    testfile_path = CMakeAnalyzer(current_build_path).get_testfile()
                    if test_path: 
                        test_path = testfile_path[0].removesuffix("CTestTestfile.cmake")
                    else:
                        test_path = current_build_path
                    CMakeProcess(current_path, current_build_path, test_path).run()

                assert False
                # TODO: Generate in Dockerfile:
                # TODO: install cmake, ctest, python3 to run this code + others?
                # TODO: with url -> get parent and current commits
                # TODO: install parent/current packages => what if there are conflicts?
                # TODO: right before the parent/current test export parent/current_flages
                # TODO: delete commits afterwards? or not if --test is set?