import os
import src.config as conf
from src.utils.crawler_utils import *
from src.utils.test_utils import *

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

            repo_path = os.path.join(self.storage['dataset'], folder)
            commit_path = os.path.join(repo_path, "test")

            commits = extract_filtered_commits(os.path.join(repo_path, self.storage['filtered']))

            if inplace:
                repo_url = f"https://github.com/{owner}/{name}.git"

                ensure_repo(repo_url, commit_path)

                for (current_sha, parent_sha) in commits:
                    checkout_commit(commit_path, parent_sha)
                    print("run_test1")
                    self.build(commit_path)

                    assert False

                    checkout_commit(commit_path, current_sha)
                    print("run_test2")

                    # TODO: run tests and save results
            
            else:
                # TODO: full -> find better way to save them in test
                for (current_sha, parent_sha) in commits:
                    parent_url = f"https://api.github.com/repos/{owner}/{name}/zipball/{parent_sha}"
                    get_commit(parent_url, os.path.join(commit_path, "parent"))
                    # run_test

                    current_url = f"https://api.github.com/repos/{owner}/{name}/zipball/{current_sha}"
                    get_commit(current_url, os.path.join(commit_path, "current"))
                    # run_test

                    print(current_url, parent_url)
                    assert False

    def build(self, test_path: str):
        # TODO: find all dependencies and install them
        # TODO: try to build the repo
        cmake_files = find_cmake_files(test_path)
        full = set()
        for cf in cmake_files:
            t = extract_cmake_packages(cf)
            full = t | full
        
        for p in full:
            print(find_apt_package_for_cmake(p))
        print(full)
        return 0
    
    def test_setup(self, test_path: str):
        # TODO: set the flags? ctest?
        return 0