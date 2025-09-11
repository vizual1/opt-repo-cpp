import os, logging
import src.config as conf
from src.utils.commit import *
from src.utils.cmake_adapter import CMakeAdapter

class Tester:
    def __init__(self):
        self.storage = conf.storage

    def test(self, inplace: bool = True, url: str = ""):
        repo_ids = extract_repo_ids(os.path.join(self.storage['repo_urls']), url)

        for repo in repo_ids:
            repo_info = repo.split("/")
            owner = repo_info[0].strip()
            name = repo_info[1].strip()
            folder = f"{owner}_{name}"

            commits = extract_filtered_commits(os.path.join(self.storage['dataset'], f"{folder}_filtered.txt"))

            for (current_sha, parent_sha) in commits:
                commit_path = os.path.join(self.storage['dataset'], f"{folder}_{current_sha}")

                # TODO: rather than running the code below, create Dockerfile for each commit
                parent_url = f"https://api.github.com/repos/{owner}/{name}/zipball/{parent_sha}"
                parent_path = os.path.join(commit_path, "parent")
                get_commit(parent_url, parent_path)
                adapter = CMakeAdapter(parent_path)
                if adapter.has_ctest():
                    flags = adapter.get_flags()
                    packages = adapter.get_packages()

                #cmake_build(parent_path)
                #self.test_commit(parent_path)

                current_url = f"https://api.github.com/repos/{owner}/{name}/zipball/{current_sha}"
                current_path = os.path.join(commit_path, "current")
                get_commit(current_url, current_path)
                cmake_build(current_path)
                self.test_commit(current_path)

                print(current_url, parent_url)

    def test_commit(self, test_path: str):
        return 0