import logging
from collections import Counter
import numpy as np
from scipy import stats

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
        self.total_repos += other.total_repos
        self.valid_repos += other.valid_repos
        return self

    def write_final_log(self) -> None:
        logging.info(f"Repositories analyzed: {self.total_repos}")
        logging.info(f"Valid repositories: {self.valid_repos}")
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

    def write_final_log(self) -> None:
        logging.info(f"Total commits analyzed: {self.num_commits}")
        logging.info(f"Performance-related commits: {self.perf_commits}")
        if self.num_commits > 0:
            logging.info(f"Optimization ratio: {self.perf_commits / self.num_commits}")
        logging.info(f"Lines added: {self.lines_added}")
        logging.info(f"Lines deleted: {self.lines_deleted}")
        logging.info(f"Total lines changed: {self.lines_added + self.lines_deleted}")
        if self.perf_commits > 0:
            logging.info(f"Average lines added per perf commit: {self.lines_added / self.perf_commits}")
            logging.info(f"Average lines deleted per perf commit: {self.lines_deleted / self.perf_commits}")
            logging.info(f"Average lines changed per perf commit: {(self.lines_added + self.lines_deleted) / self.perf_commits}")

def is_exec_time_improvement_significant(
    min_exec_time_improvement: float,
    min_p_value: float,
    v1_times: list[float],
    v2_times: list[float]
) -> bool:
    if len(v1_times) != len(v2_times):
        raise ValueError("v1_times and v2_times must have the same length")
    v1 = np.asarray(v1_times, dtype=float)
    v2 = np.asarray(v2_times, dtype=float)

    c = 1.0 - min_exec_time_improvement # we test μ1 < c * μ2
    v2_scaled = c * v2

    # Welch's t-test, one-sided: H1: mean(v1) < mean(v2_scaled)
    res = stats.ttest_ind(v1, v2_scaled, equal_var=False, alternative='less')
    logging.info(f"T-test result: {res.statistic} (statistic), {res.pvalue} (pvalue)") # type: ignore
    return bool(res.pvalue < min_p_value) # type: ignore