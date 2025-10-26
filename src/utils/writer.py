import os, logging
import src.config as conf
from github.Commit import Commit
from src.utils.stats import CommitStats
from typing import Optional
from pathlib import Path

class Writer:
    def __init__(self, repo_name: str):
        try:
            self.owner, self.name = repo_name.split("/", 1)
        except ValueError:
            raise ValueError(f"Invalid repo name format: '{repo_name}'. Expected '<owner>/<repo>'.")
        
        self.storage = conf.storage
        self.file: Optional[str] = None

        for key, path in self.storage.items():
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    def write_repo(self, write: str = "") -> None:
        msg = f"https://github.com/{self.owner}/{self.name}\n"
        path = Path(write or self.storage["repo_urls"])
        self._write(path, msg)

    def write_commit(self, commit: Commit, separate: bool) -> CommitStats:
        stats = CommitStats()

        stats.perf_commits += 1
        total_add = sum(f.additions for f in commit.files)
        total_del = sum(f.deletions for f in commit.files)

        stats.lines_added += total_add
        stats.lines_deleted += total_del

        current_sha = commit.sha
        parent_sha = commit.parents[0].sha if commit.parents else "None"

        self.file = f"{self.owner}_{self.name}_filtered.txt"
        msg = f"{current_sha} | {parent_sha} | +{total_add} | -{total_del} | {total_add + total_del}\n" 
        path = Path(self.storage["store_commits"]) / self.file
        self._write(path, msg)
        
        # saves each commit version to file with patch information
        if separate:
            file = f"{self.owner}_{self.name}_{current_sha}.txt"
            msg = f"{current_sha} | {parent_sha}"
            final_msg: list[str] = [msg, commit.commit.message]
            for f in commit.files:
                final_msg.append(f.patch)
            path = Path(self.storage["store_commits"]) / file
            self._write(path, "\n".join(final_msg))

        return stats

    def write_improve(self, new_sha: str, old_sha: str) -> None:
        self.file = f"{self.owner}_{self.name}.txt"
        path = Path(self.storage["performance_commits"]) / self.file
        msg = f"{new_sha} | {old_sha}\n"
        self._write(path, msg)

    def _write(self, path: Path, msg: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", errors="ignore") as f:
                f.write(msg)
            logging.info(f"[{self.owner}/{self.name}] Wrote data to {path}")
        except (OSError, IOError) as e:
            logging.error(f"[{self.owner}/{self.name}] Failed to write to {path}: {e}", exc_info=True)