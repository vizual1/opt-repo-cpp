import logging
from collections import Counter

class RepoStats:
    def __init__(self):
        self.test_dirs = Counter()
        self.test_flags = Counter()
        self.pack_manager = Counter()
        self.pack_files = Counter()
        self.dependencies = Counter()
        self.total_repos: int = 0
        self.valid_repos: int = 0

    def __iadd__(self, other: 'RepoStats') -> 'RepoStats':
        self.test_dirs += other.test_dirs
        self.test_flags += other.test_flags
        self.pack_manager += other.pack_manager
        self.pack_files += other.pack_files
        self.dependencies += other.dependencies
        return self

    def write_final_log(self):
        logging.info(f"Final Counter: {self.test_dirs}")
        logging.info(f"Final Flags: {self.test_flags}")
        logging.info(f"Final Package Managers: {self.pack_manager}")
        logging.info(f"Final Package Files: {self.pack_files}")
        logging.info(f"Final Dependencies: {self.dependencies}")

class CommitStats:
    def __init__(self):
        self.num_commits = 0
        self.perf_commits = 0
        self.lines_added = 0
        self.lines_deleted = 0

    def __iadd__(self, other: 'CommitStats') -> 'CommitStats':
        self.num_commits += other.num_commits
        self.perf_commits += other.perf_commits
        self.lines_added += other.lines_added
        self.lines_deleted += other.lines_deleted
        return self

    def write_final_log(self):
        logging.info(f"Number of commits: {self.num_commits}")
        logging.info(f"Number of filtered commits: {self.perf_commits}")
        logging.info(f"Optimization Ratio: {self.perf_commits/self.num_commits}")
        logging.info(f"Number of lines added: {self.lines_added}")
        logging.info(f"Number of lines deleted: {self.lines_deleted}")
        logging.info(f"Number of lines changed: {self.lines_added + self.lines_deleted}")
        logging.info(f"Average number of lines added: {self.lines_added/self.perf_commits}")
        logging.info(f"Average number of lines deleted: {self.lines_deleted/self.perf_commits}")
        logging.info(f"Average number of lines changed: {(self.lines_added + self.lines_deleted)/self.perf_commits}")
    