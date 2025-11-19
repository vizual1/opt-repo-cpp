import logging, math
from datetime import datetime
from src.utils.parser import parse_single_ctest_output
import numpy as np
from scipy import stats
from github.Commit import Commit
from github.Repository import Repository
from src.core.filter.commit_filter import CommitFilter
from src.config.config import Config

class TestAnalyzer:
    def __init__(self, config: Config, new_single_tests: dict[str, list[float]], old_single_tests: dict[str, list[float]]):
        self.config = config
        self.new_single_tests = new_single_tests
        self.old_single_tests = old_single_tests

        self.warmup = self.config.testing.warmup
        self.commit_test_times = self.config.testing.commit_test_times
        self.min_exec_time_improvement: float = self.config.commits_time['min-exec-time-improvement']
        self.min_p_value: float = self.config.commits_time['min-p-value']

    def relative_improvement(self, old_times: list[float], new_times: list[float]):
        """relative improvement of new_times to old_times"""
        if sum(old_times) > 0.0:
            return (sum(old_times) - sum(new_times)) / sum(old_times)
        return 0.0
    
    def get_overall_change(self) -> float:
        total_old = 0.0
        total_new = 0.0

        for test_name in self.new_single_tests.keys():
            new_times = self.new_single_tests[test_name][self.warmup:]
            old_times = self.old_single_tests[test_name][self.warmup:]
            total_new += sum(new_times)
            total_old += sum(old_times)

        if total_old == 0.0:
            return 0.0
        return (total_old - total_new) / total_old

    
    def get_improvement_p_value(
        self,
        old_times: list[float],
        new_times: list[float]
    ) -> float:
        """
        Perform a one-sided Welch's t-test to determine whether the *new* version
        is significantly faster than the *old* version by at least the configured
        minimum improvement threshold.

        What hypothesis we test:
            Let old_times = X, new_times = Y.
            Let δ = min_exec_time_improvement (e.g., 0.05 = require 5% speedup).

            We test the hypothesis:

                H0: mean(X) >= (1 - δ) * mean(Y)
                H1: mean(X) <  (1 - δ) * mean(Y)

            Meaning:
                H0: The old version is NOT slower than the new version by δ.
                H1: The old version IS slower than the new version by δ
                    -> new version is faster by at least δ.

        Why the scaling (c * new):
            We rewrite the inequality:
                mean(X) < (1 - δ) * mean(Y)

            Let c = (1 - δ).
            We test mean(X) < mean(c * Y).

            This allows us to use a standard one-sided Welch t-test comparing
            X vs. (c * Y).

        Interpretation of the p-value:
            - Low p-value (< min_p_value) means:
                    Strong evidence that the new version is significantly faster
                    by at least the requested threshold (δ).
            - High p-value means:
                    We cannot conclude the new version is faster by δ.

        Returns:
            float: p-value of the hypothesis test.
        """
        if len(old_times) != len(new_times):
            raise ValueError("v1_times and v2_times must have the same length")
        old = np.asarray(old_times, dtype=float)
        new = np.asarray(new_times, dtype=float)

        c = 1.0 - self.min_exec_time_improvement # we test μ1 < c * μ2
        new_scaled = c * new

        # Welch's t-test, one-sided: H1: mean(v1) < mean(v2_scaled)
        res = stats.ttest_ind(old, new_scaled, equal_var=False, alternative='less')
        logging.info(f"T-test result: {res.pvalue} (pvalue)") # type: ignore
        return float(res.pvalue) # type: ignore
    
    
    def get_significant_test_time_changes(self) -> dict[str, list[str]]:
        significant_test_time_changes = {'old_outperforms_new': [], 'new_outperforms_old': []}

        for test_name in self.new_single_tests.keys():
            new_times = self.new_single_tests[test_name][self.warmup:]
            old_times = self.old_single_tests[test_name][self.warmup:]
            if self.get_improvement_p_value(old_times, new_times) < self.min_p_value:
                significant_test_time_changes['new_outperforms_old'].append(test_name)
                logging.info(f"new_outperforms_old improvement: {self.relative_improvement(new_times, old_times)*100}%")
            if self.get_improvement_p_value(new_times, old_times) < self.min_p_value:
                significant_test_time_changes['old_outperforms_new'].append(test_name)
                logging.info(f"old_outperforms_new improvement: {self.relative_improvement(old_times, new_times)*100}%")
            
        logging.info(significant_test_time_changes)
        return significant_test_time_changes
        
    def create_test_log(self, commit: Commit, repo: Repository, old_sha: str, new_sha: str, 
                        old_full_times: list[float], new_full_times: list[float],
                        old_commands: list[str], new_commands: list[str]) -> dict:
        message = commit.commit.message
        patches = self.get_diff(commit)

        commit_filter = CommitFilter(commit, self.config, repo)
        extracted_refs = commit_filter.extract_fixed_issues()
        gh_refs = [
            (ref_type, number, issue.title, issue.body, issue) 
            for number, ref_type in extracted_refs.items()
            if (issue := repo.get_issue(number))
        ]

        metadata = {
            "collection_date": datetime.now().isoformat(),
            "repository": f"https://github.com/{repo.full_name}",
            "repository_name": repo.full_name
        }
        commit_info = {
            "old_sha": old_sha,
            "new_sha": new_sha,
            "commit_message": message,
            "commit_date": commit.commit.author.date.isoformat(),
            "patch": patches,
            "files_changed": [
                {
                    "filename": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "changes": f.changes,
                    "patch": f.patch
                }
                for f in commit.files or []
            ],
            "lines_added": commit.stats.additions,
            "lines_removed": commit.stats.deletions, 
        }
        build_info = {
            "old_build_script": "#!/bin/bash\n" + "\n".join(old_commands[0:2]),
            "new_build_script": "#!/bin/bash\n" + "\n".join(old_commands[0:2]),
            "old_test_script": "#!/bin/bash\n" + "\n".join(old_commands[2:]),
            "new_test_script": "#!/bin/bash\n" + "\n".join(old_commands[2:]),
            "build_system": "cmake"
        }

        pvalue = self.get_improvement_p_value(new_full_times[self.warmup:], old_full_times[self.warmup:]) 
        old = np.asarray(old_full_times[self.warmup:], float)
        new = np.asarray(new_full_times[self.warmup:], float)
        performance_analysis = {
            "is_significant": pvalue < self.min_p_value,
            "p_value": pvalue,
            "relative_improvement": self.relative_improvement(new_full_times[self.warmup:], old_full_times[self.warmup:]),
            "absolute_improvement_ms": float((np.mean(old) - np.mean(new)) * 1000),
            "old_mean_ms": float(np.mean(old) * 1000),
            "new_mean_ms": float(np.mean(new) * 1000),
            "old_std_ms": float(np.std(old, ddof=1) * 1000),
            "new_std_ms": float(np.std(new, ddof=1) * 1000),
            "effect_size_cohens_d": self.cohens_d(old, new),
            "old_ci95_ms": self.ci95(old_full_times[self.warmup:]),
            "new_ci95_ms": self.ci95(new_full_times[self.warmup:]),
            "old_ci99_ms": self.ci99(old_full_times[self.warmup:]),
            "new_ci99_ms": self.ci99(new_full_times[self.warmup:]),
            "old_times_s": old_full_times,
            "new_times_s": new_full_times
        }

        significant_test_time_changes = self.get_significant_test_time_changes()
        tests = {
            "total_tests": len(self.new_single_tests.keys()),
            "significant_improvements": len(significant_test_time_changes['new_outperforms_old']),
            "significant_improvements_tests": significant_test_time_changes['new_outperforms_old'],
            "significant_regressions": len(significant_test_time_changes['old_outperforms_new']),
            "significant_regressions_tests": significant_test_time_changes['old_outperforms_new'],
            "tests": []
        }
        for test_name in self.new_single_tests.keys():
            new_times = self.new_single_tests[test_name][self.warmup:]
            old_times = self.old_single_tests[test_name][self.warmup:]
            pvalue = self.get_improvement_p_value(new_times, old_times) 
            tests["tests"].append({
                "test_name": test_name,
                "is_significant": pvalue < self.min_p_value,
                "p_value": pvalue,
                "relative_improvement": self.relative_improvement(new_times, old_times),
                "absolute_improvement_ms": float((np.mean(old_times) - np.mean(new_times)) * 1000),
                "old_mean_ms": float(np.mean(old_times) * 1000),
                "new_mean_ms": float(np.mean(new_times) * 1000),
                "old_std_ms": float(np.std(old_times, ddof=1) * 1000),
                "new_std_ms": float(np.std(new_times, ddof=1) * 1000),
                "effect_size_cohens_d": self.cohens_d(old_times, new_times),
                "old_ci95_ms": self.ci95(old_times),
                "new_ci95_ms": self.ci95(new_times),
                "old_ci99_ms": self.ci99(old_times),
                "new_ci99_ms": self.ci99(new_times),
                "new_times": new_times,
                "old_times": old_times
            })

        issues = [
            {
                "number": number,
                "url": f"https://github.com/{repo.full_name}/issues/{number}",
                "title": title,
                "body": body,
                "created_at": issue.created_at.isoformat()
            }
            for ref in gh_refs
            if (ref_type := ref[0]) == "issue" and (number := ref[1]) and (title := ref[2]) and (body := ref[3]) and (issue := ref[4])
        ]

        pull_requests = [
            {
                "number": number,
                "url": f"https://github.com/{repo.full_name}/pull/{number}",
                "title": title,
                "body": body,
                "merged_at": issue.pull_request.merged_at.isoformat() if issue.pull_request and issue.pull_request.merged_at else None
            }
            for ref in gh_refs
            if (ref_type := ref[0]) == "pull_request" and (number := ref[1]) and (title := ref[2]) and (body := ref[3]) and (issue := ref[4])
        ]

        results = {
            "metadata": metadata,
            "commit_info": commit_info,
            "issues": issues, 
            "pull_requests": pull_requests,
            "build_info": build_info,
            "performance_analysis": performance_analysis,
            "tests": tests,
            "logs": {
                "full_log_path": "/logs/full.log",
                "config_log_path": "/logs/config.log",
                "build_log_path": "/logs/build.log",
                "test_log_path": "/logs/test.log",
                "build_success": True,
                "test_success": True
            },
            "raw_timing_data": {
                "warmup_runs": self.config.testing.warmup,
                "measurement_runs": self.config.testing.commit_test_times,
                "min_exec_time_improvement": self.min_exec_time_improvement,
                "min_p_value": self.min_p_value
            }

        }
        return results

    def get_diff(self, commit: Commit) -> str:
        diff_lines: list[str] = []
        for f in commit.files:
            if f.patch:
                diff_lines.append(f"--- {f.filename}")
                patch = f.patch
                diff_lines.append(patch)
        return "\n".join(diff_lines)
    
    def cohens_d(self, old, new):
        """
        Compute Cohen's d effect size between old and new execution times.

        What it measures:
            - The magnitude of the performance improvement/regression.
            - It is scale-free and independent of units (s, ms, etc).
            - It shows *how big* the difference is, not just whether it is statistically significant.

        Interpretation:
            d = 0.2  -> small effect
            d = 0.5  -> medium effect
            d = 0.8  -> large effect
            d > 1.0  -> very large effect

        Sign convention:
            Positive d  -> new is faster (mean(new) < mean(old))
            Negative d  -> new is slower (regression)

        Formula:
            d = (mean(old) - mean(new)) / pooled_std
            where pooled_std is the pooled standard deviation of both samples.

        Why we use it:
            - p-values alone do not tell how *big* the improvement is.
            - Cohen's d tells how meaningful the difference is in practical terms.
        """
        old = np.asarray(old, float)
        new = np.asarray(new, float)
        n1, n2 = len(old), len(new)
        s1, s2 = np.var(old, ddof=1), np.var(new, ddof=1)
        pooled = np.sqrt(((n1 - 1)*s1 + (n2 - 1)*s2) / (n1 + n2 - 2))
        return (np.mean(old) - np.mean(new)) / pooled

    def ci95(self, xs: list[float]) -> tuple[float, float]:
        """
        Compute a 95% confidence interval for the mean execution time.

        What it measures:
            - A range where the true mean execution time is expected to lie
            with 95% probability.

        Interpretation:
            If CI95 for old is (100ms, 110ms)
            and CI95 for new is (80ms, 90ms),
            the intervals do not overlap -> strong indication of improvement.

        Why we use confidence intervals:
            - They show the stability and variability of the benchmark.
            - They are a more intuitive alternative to p-values.
            - Narrow CI -> stable performance
            - Wide CI -> noisy benchmark, possible measurement issues.

        Returns:
            (ci_low_ms, ci_high_ms)
        """
        arr = np.asarray(xs, dtype=float)
        n = len(arr)
        if n < 2:
            return (0.0, 0.0)
        se = np.std(arr, ddof=1) / math.sqrt(n)
        h = se * stats.t.ppf(0.975, n-1)
        mean = np.mean(arr)
        return (float(mean - h)*1000, float(mean + h)*1000)
    
    def ci99(self, xs: list[float]) -> tuple[float, float]:
        """
        Return the 99% confidence interval (lower_ms, upper_ms) for the mean.
        """
        arr = np.asarray(xs, dtype=float)
        n = len(arr)
        if n < 2:
            return (0.0, 0.0)

        se = np.std(arr, ddof=1) / math.sqrt(n)
        h = se * stats.t.ppf(0.995, n - 1)  # 99%: use 0.995
        mean = np.mean(arr)

        # return in milliseconds
        return (float((mean - h) * 1000), float((mean + h) * 1000))