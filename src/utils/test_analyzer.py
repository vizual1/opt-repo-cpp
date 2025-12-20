import logging, math
from datetime import datetime
import numpy as np
from scipy import stats
from github.Commit import Commit
from github.Repository import Repository
from src.core.filter.commit_filter import CommitFilter
from src.config.config import Config

def safe_float(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "NaN"
    return float(x)

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
        if len(old_times) != len(new_times):
            raise ValueError("v1_times and v2_times must have the same length")
        old = np.asarray(old_times, dtype=float)
        new = np.asarray(new_times, dtype=float)

        c = 1.0 - self.min_exec_time_improvement # we test μ1 < c * μ2
        old_scaled = c * old

        # Welch's t-test, one-sided: H1: mean(v1) < mean(v2_scaled)
        res = stats.ttest_ind(new, old_scaled, equal_var=False, alternative='less')
        logging.debug(f"T-test result: {res.pvalue} (pvalue)") # type: ignore
        return float(res.pvalue) # type: ignore
    
    def get_pair_improvement_p_value(
        self,
        old_times: list[float],
        new_times: list[float]
    ) -> float:
        old = np.asarray(old_times, dtype=float)
        new = np.asarray(new_times, dtype=float)
        if old.shape != new.shape:
            raise ValueError("old_times and new_times must have same length")

        # Differences: positive = old slower than new (i.e., improvement)
        diff = old - new

        # Convert relative threshold to absolute delta (use mean(old) as baseline)
        delta = self.min_exec_time_improvement * old.mean()

        # Adjust diffs by delta so test is H0: mean(diff) <= delta  => H1: mean(diff) > delta
        adjusted = diff - delta

        # One-sample t-test (one-sided greater)
        res = stats.ttest_1samp(adjusted, popmean=0.0, alternative='greater')
        return res.pvalue # type: ignore
    
    def get_wilcoxon_pvalue(
        self,
        old_times: list[float],
        new_times: list[float]
    ) -> float:
        old = np.asarray(old_times, dtype=float)
        new = np.asarray(new_times, dtype=float)
        diff = old - new
        delta = self.min_exec_time_improvement * old.mean()
        adjusted = diff - delta
        # SciPy supports alternative='greater'
        res = stats.wilcoxon(adjusted, alternative='greater', zero_method='wilcox')
        return float(res.pvalue) # type: ignore
    
    def get_mannwhitney_pvalue(
        self,
        old_times: list[float],
        new_times: list[float]
    ) -> float:
        old = np.asarray(old_times, dtype=float)
        new = np.asarray(new_times, dtype=float)
        if len(old) != len(new):
            raise ValueError("old_times and new_times must have same length")

        # One-sided: H1: new < old (new is faster)
        res = stats.mannwhitneyu(new, old, alternative='less')
        return float(res.pvalue)
    
    def is_mannwhitney_significant(
        self,
        old_times: list[float],
        new_times: list[float],
    ) -> bool:
        p_mwu = self.get_mannwhitney_pvalue(old_times, new_times)
        delta  = self.relative_improvement(old_times, new_times)
        return bool(p_mwu < self.min_p_value) and bool(delta > self.min_exec_time_improvement)
    
    def get_binom_improvement_p_value(
        self,
        old_times: list[float],
        new_times: list[float]
    ) -> float:
        """
        Test if the median of v2 is significantly less than min-exec-time-improvement * the median of v1.

        Args:
            v1: List of values
            v2: List of values

        Returns:
            p-value
        """
        old = np.asarray(old_times, dtype=float)
        new = np.asarray(new_times, dtype=float)
        if old.shape != new.shape:
            raise ValueError("old_times and new_times must have same length")

        c = 1.0 - self.min_exec_time_improvement  # we test μ2 < c * μ1
        old_scaled = c * old
        diff = new - old_scaled

        wins = np.sum(diff < 0)   # V2 achieves at least 'margin' speedup
        losses = np.sum(diff > 0) # V2 fails to achieve the margin
        n = wins + losses

        if n == 0:
            logging.error("All pairs are ties or NaN after applying the margin; cannot perform sign test.")
            return 0.0
        
        # Exact one-sided binomial test: H1 is 'wins' > 0.5
        res = stats.binomtest(k=wins, n=n, p=0.5, alternative="greater")

        return float(res.pvalue)

    def get_significant_test_time_changes(
            self, f
        ) -> dict[str, list[str]]:
        significant_test_time_changes = {'old_outperforms_new': [], 'new_outperforms_old': []}

        for test_name in self.new_single_tests.keys():
            new_times = self.new_single_tests[test_name][self.warmup:]
            old_times = self.old_single_tests[test_name][self.warmup:]
            if any(t <= 0.005 for t in new_times) or any(t <= 0.005 for t in old_times):
                continue
            if f(old_times, new_times) < self.min_p_value:
                significant_test_time_changes['new_outperforms_old'].append(test_name)
                logging.debug(f"new_outperforms_old improvement: {self.relative_improvement(old_times, old_times)*100}%")
            if f(new_times, old_times) < self.min_p_value:
                significant_test_time_changes['old_outperforms_new'].append(test_name)
                logging.debug(f"old_outperforms_new improvement: {self.relative_improvement(old_times, new_times)*100}%")
            
        logging.debug(significant_test_time_changes)
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

        pvalue = self.get_improvement_p_value(old_full_times[self.warmup:], new_full_times[self.warmup:]) 
        pair_pvalue = self.get_pair_improvement_p_value(old_full_times[self.warmup:], new_full_times[self.warmup:])
        binom_pvalue = self.get_binom_improvement_p_value(old_full_times[self.warmup:], new_full_times[self.warmup:])
        wilcoxon_pvalue = self.get_wilcoxon_pvalue(old_full_times[self.warmup:], new_full_times[self.warmup:])
        mannwhitney_pvalue = self.get_mannwhitney_pvalue(old_full_times[self.warmup:], new_full_times[self.warmup:])
        old = np.asarray(old_full_times[self.warmup:], float)
        new = np.asarray(new_full_times[self.warmup:], float)
        performance_analysis = {
            "is_significant": bool(pvalue < self.min_p_value),
            "p_value": safe_float(pvalue),
            "is_pair_significant": bool(pair_pvalue < self.min_p_value),
            "pair_p_value": safe_float(pair_pvalue),
            "is_binom_significant": bool(binom_pvalue < self.min_p_value),
            "binom_p_value": safe_float(binom_pvalue),
            "is_wilcoxon_significant": bool(wilcoxon_pvalue < self.min_p_value),
            "wilcoxon_p_value": safe_float(wilcoxon_pvalue), 
            "is_mannwhitney_significant": bool(self.is_mannwhitney_significant(old_full_times[self.warmup:], new_full_times[self.warmup:])),
            "mannwhitney_p_value": safe_float(mannwhitney_pvalue),
            "relative_improvement": safe_float(self.relative_improvement(old_full_times[self.warmup:], new_full_times[self.warmup:])),
            "absolute_improvement_ms": safe_float((np.mean(old) - np.mean(new)) * 1000),
            "old_mean_ms": safe_float(np.mean(old) * 1000),
            "new_mean_ms": safe_float(np.mean(new) * 1000),
            "old_std_ms": safe_float(np.std(old, ddof=1) * 1000),
            "new_std_ms": safe_float(np.std(new, ddof=1) * 1000),
            "effect_size_cohens_d": safe_float(self.cohens_d(old, new)),
            "old_ci95_ms": self.ci95(old_full_times[self.warmup:]),
            "new_ci95_ms": self.ci95(new_full_times[self.warmup:]),
            "old_ci99_ms": self.ci99(old_full_times[self.warmup:]),
            "new_ci99_ms": self.ci99(new_full_times[self.warmup:]),
            "new_times_s": new_full_times,
            "old_times_s": old_full_times
        }

        significant_test_time_changes = self.get_significant_test_time_changes(self.get_improvement_p_value)
        significant_pair_test_time_changes = self.get_significant_test_time_changes(self.get_pair_improvement_p_value)
        significant_binom_test_time_changes = self.get_significant_test_time_changes(self.get_binom_improvement_p_value)
        significant_wilcoxon_test_time_changes = self.get_significant_test_time_changes(self.get_wilcoxon_pvalue)
        significant_mannwhitney_test_time_changes = self.get_significant_test_time_changes(self.get_mannwhitney_pvalue)
        tests = {
            "total_tests": len(self.new_single_tests.keys()),
            "significant_improvements": len(significant_test_time_changes['new_outperforms_old']),
            "significant_improvements_tests": significant_test_time_changes['new_outperforms_old'],
            "significant_regressions": len(significant_test_time_changes['old_outperforms_new']),
            "significant_regressions_tests": significant_test_time_changes['old_outperforms_new'],
            "significant_pair_improvements": len(significant_pair_test_time_changes['new_outperforms_old']),
            "significant_pair_improvements_tests": significant_pair_test_time_changes['new_outperforms_old'],
            "significant_pair_regressions": len(significant_pair_test_time_changes['old_outperforms_new']),
            "significant_pair_regressions_tests": significant_pair_test_time_changes['old_outperforms_new'],
            "significant_binom_improvements": len(significant_binom_test_time_changes['new_outperforms_old']),
            "significant_binom_improvements_tests": significant_binom_test_time_changes['new_outperforms_old'],
            "significant_binom_regressions": len(significant_binom_test_time_changes['old_outperforms_new']),
            "significant_binom_regressions_tests": significant_binom_test_time_changes['old_outperforms_new'],
            "significant_wilcoxon_improvements": len(significant_wilcoxon_test_time_changes['new_outperforms_old']),
            "significant_wilcoxon_improvements_tests": significant_wilcoxon_test_time_changes['new_outperforms_old'],
            "significant_wilcoxon_regressions": len(significant_wilcoxon_test_time_changes['old_outperforms_new']),
            "significant_wilcoxon_regressions_tests": significant_wilcoxon_test_time_changes['old_outperforms_new'],
            "significant_mannwhitney_improvements": len(significant_mannwhitney_test_time_changes['new_outperforms_old']),
            "significant_mannwhitney_improvements_tests": significant_mannwhitney_test_time_changes['new_outperforms_old'],
            "significant_mannwhitney_regressions": len(significant_mannwhitney_test_time_changes['old_outperforms_new']),
            "significant_mannwhitney_regressions_tests": significant_mannwhitney_test_time_changes['old_outperforms_new'],
            "tests": []
        }
        for test_name in self.new_single_tests.keys():
            new_times = self.new_single_tests[test_name][self.warmup:]
            old_times = self.old_single_tests[test_name][self.warmup:]
            if any(t <= 0.005 for t in new_times) or any(t <= 0.005 for t in old_times): #0.0 in new_times or 0.0 in old_times:
                continue
            pvalue = self.get_improvement_p_value(old_times, new_times) 
            pair_pvalue = self.get_pair_improvement_p_value(old_times, new_times)
            binom_pvalue = self.get_binom_improvement_p_value(old_times, new_times)
            wilcoxon_pvalue = self.get_wilcoxon_pvalue(old_times, new_times)
            mannwhitney_pvalue = self.get_mannwhitney_pvalue(old_times, new_times)
            tests["tests"].append({
                "test_name": test_name,
                "is_significant": bool(pvalue < self.min_p_value),
                "p_value": safe_float(pvalue),
                "is_pair_significant": bool(pair_pvalue < self.min_p_value),
                "pair_p_value": safe_float(pair_pvalue),
                "is_binom_significant": bool(binom_pvalue < self.min_p_value),
                "binom_p_value": safe_float(binom_pvalue),
                "is_wilcoxon_significant": bool(wilcoxon_pvalue < self.min_p_value),
                "wilcoxon_p_value": safe_float(wilcoxon_pvalue), 
                "is_mannwhitney_significant": bool(self.is_mannwhitney_significant(old_times, new_times)),
                "mannwhitney_p_value": safe_float(mannwhitney_pvalue),
                "relative_improvement": safe_float(self.relative_improvement(old_times, new_times)),
                "absolute_improvement_ms": safe_float((np.mean(old_times) - np.mean(new_times)) * 1000),
                "old_mean_ms": safe_float(np.mean(old_times) * 1000),
                "new_mean_ms": safe_float(np.mean(new_times) * 1000),
                "old_std_ms": safe_float(np.std(old_times, ddof=1) * 1000),
                "new_std_ms": safe_float(np.std(new_times, ddof=1) * 1000),
                "effect_size_cohens_d": safe_float(self.cohens_d(old_times, new_times)),
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
    
    def cohens_d(self, old, new) -> float:
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