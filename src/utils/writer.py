import os, logging
import src.config as conf
from github.Commit import Commit
from src.utils.stats import CommitStats

class Writer:
    def __init__(self, repo_name: str):
        self.owner, self.name = repo_name.split("/")
        self.storage = conf.storage
        self.file: str = ""

    def write_repo(self, write: str = "") -> None:
        msg = f"https://github.com/{self.owner}/{self.name}\n"
        if write:
            path = write
        else:
            path = self.storage['repo_urls']
        logging.info(f"Written to {path}")
        self._write(path, msg)

    def write_commit(self, commit: Commit, separate: bool) -> CommitStats:
        stats = CommitStats()
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

        self.file = f"{self.owner}_{self.name}_filtered.txt"
        msg = f"{current_sha} | {commit.parents[0].sha or 'None'} | +{total_add} | -{total_del} | {total_add + total_del}\n" 
        path = os.path.join(self.storage['store_commits'], self.file)
        self._write(path, msg)
        
        # saves each commit version to file with patch information
        if separate:
            file = f"{self.owner}_{self.name}_{current_sha}.txt"
            msg = f"{current_sha} | {commit.parents[0].sha or 'None'}"
            final_msg: list[str] = [msg, commit.commit.message]
            for f in commit.files:
                final_msg.append(f.patch)
            path = os.path.join(self.storage['store_commits'], file)
            self._write(path, "\n".join(final_msg))
        
        return stats

    def _write(self, path: str, msg: str):
        try:
            with open(path, 'a', encoding="utf-8", errors='ignore') as f:
                f.write(msg)
        except (OSError, IOError) as e:
            logging.error(f"Failed to write to {path}: {e}", exc_info=True)