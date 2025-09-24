import os
import src.config as conf
from github.Commit import Commit
from src.utils.statistics import CommitStats

class Writer:
    def __init__(self, repo_name: str):
        self.owner, self.name = repo_name.split("/")
        self.storage = conf.storage

    def write_repo(self):
        msg = f"https://github.com/{self.owner}/{self.name}"
        path = os.path.join(self.storage['dataset'], self.storage['repo_urls'])
        with open(path, 'a', encoding="utf-8", errors='ignore') as f:
            f.write(msg + "\n")

    def write_commit(self, stats: CommitStats, commit: Commit, separate: bool):
        stats.perf_commits += 1

        if commit.parents:
            parent_sha = commit.parents[0].sha
        else:
            parent_sha = None 

        total_add = sum(f.additions for f in commit.files)
        total_del = sum(f.deletions for f in commit.files)

        stats.lines_added += total_add
        stats.lines_deleted += total_del

        current_sha = commit.sha

        file = f"{self.owner}_{self.name}_filtered.txt"
        msg = f"{current_sha} | {commit.parents[0].sha or 'None'} | +{total_add} | -{total_del} | {total_add + total_del}" 
        path = os.path.join(self.storage['dataset'], file)
        with open(path, 'a', encoding="utf-8", errors='ignore') as f:
            f.write(msg + "\n")
        
        # saves each commit version to file with patch information
        if separate:
            file = f"{self.owner}_{self.name}_{current_sha}.txt"
            msg = f"{current_sha} | {commit.parents[0].sha or 'None'} \n {commit.commit.message} \n"
            for f in commit.files:
                msg += f"{f.patch} \n"
            path = os.path.join(self.storage['dataset'], file)
            with open(path, 'a', encoding="utf-8", errors='ignore') as f:
                f.write(msg + "\n")