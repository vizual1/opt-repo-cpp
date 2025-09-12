import logging
import src.config as conf
from src.utils.commit import *
from src.utils.cmake_adapter import CMakeAdapter
from src.utils.conflict_resolver import *

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
                parent_url = f"https://api.github.com/repos/{owner}/{name}/zipball/{parent_sha}"
                parent_path = os.path.join(commit_path, "parent")
                get_commit(parent_url, parent_path)
                parent_adapter = CMakeAdapter(parent_path)

                current_url = f"https://api.github.com/repos/{owner}/{name}/zipball/{current_sha}"
                current_path = os.path.join(commit_path, "current")
                get_commit(current_url, current_path)
                current_adapter = CMakeAdapter(current_path)
                if parent_adapter.has_ctest() and current_adapter.has_ctest():
                    parent_flags = parent_adapter.get_flags()
                    parent_packages = parent_adapter.get_packages()

                    current_flags = current_adapter.get_flags()
                    current_packages = current_adapter.get_packages()

                    logging.info(f"Parent flags {parent_flags}")
                    logging.info(f"Current flags {current_flags}")

                    logging.info(f"CTest found in commit {current_sha}.")

                    if ignore_conflict:
                        logging.warning("Package conflicts ignored.")
                    
                    if ignore_conflict or not check_package_conflict(parent_packages, current_packages):
                        print("does something")

                assert False
                # TODO: Generate in Dockerfile:
                # TODO: install cmake, ctest, python3 to run this code + others?
                # TODO: with url -> get parent and current commits
                # TODO: install parent/current packages => what if there are conflicts?
                # TODO: right before the parent/current test export parent/current_flages
                # TODO: delete commits afterwards? or not if --test is set?