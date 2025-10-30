import logging
from tqdm import tqdm
from src.utils.crawler import RepositoryCrawler
from src.filter.structure_filter import StructureFilter
from src.filter.commit_filter import CommitFilter
from src.filter.process_filter import ProcessFilter
from src.utils.stats import RepoStats, CommitStats
from src.utils.writer import Writer
from src.utils.tester import CommitTester
from src.utils.dataclasses import Config
from github.Repository import Repository
import numpy as np
from scipy import stats
from contextlib import contextmanager 
from pathlib import Path
from typing import Generator, Optional, Any

class CrawlerPipeline:
    """
    This class crawls popular GitHub repositories.
    """
    def __init__(self, config: Config):
        self.config = config

    def get_repos(self) -> list[str]:
        crawler = RepositoryCrawler(config=self.config)
        repos = crawler.get_repos()
        logging.info(f"Found {len(repos)} repositories from crawler.")
        for repo in repos:
            Writer(repo, self.config.output or self.config.storage['popular']).write_repo()
        return repos
    

class RepositoryPipeline:
    """
    This class takes a list of repositories, and tests and validates them.
    """
    def __init__(self, config: Config):
        self.config = config
        self.stats = RepoStats()
        self.valid_repos: list[Repository] = []

    def get_repos(self) -> list[str]:
        crawler = RepositoryCrawler(config=self.config)
        return crawler.get_repos()

    def test_repos(self) -> None:
        crawler = RepositoryCrawler(self.config)
        repos = crawler.get_repos()
        if not repos:
            logging.warning("No repositories found.")
            return

        logging.info(f"Found {len(repos)} repositories.")
        for repo in tqdm(repos, total=len(repos), desc=f"Testing repositories..."):
            try:
                structure = StructureFilter(repo, self.config.git)
                process = ProcessFilter(repo, self.config)

                if structure.is_valid() and process.valid_run("_".join(repo.split("/"))):
                    self.valid_repos.append(structure.repo)
                    if self.config.popular or self.config.output:
                        Writer(structure.repo.full_name, self.config.output).write_repo()

                elif self.config.output:
                    Writer(structure.repo.full_name, self.config.output_fail).write_repo()

            except Exception as e:
                logging.exception(f"[{repo}] Error processing repository: {e}")

           
    def analyze_repos(self) -> None:
        crawler = RepositoryCrawler(config=self.config)
        repos = crawler.get_repos()
        if not repos:
            logging.warning("No repositories found.")
            return
        
        logging.info(f"Found {len(repos)} repositories.")
        for repo in tqdm(repos, total=len(repos), desc=f"Analyzing repositories..."):
            try:
                structure = StructureFilter(repo, self.config.git)
                if structure.is_valid() and (self.config.popular or self.config.output):
                    Writer(structure.repo.full_name, self.config.output).write_repo()
                self.stats += structure.stats

            except Exception as e:
                logging.exception(f"[{repo}] Error analyzing: {e}")

        self.stats.write_final_log()


class CommitPipeline():
    """
    This class filters and saves the commit history of a repository.
    """
    def __init__(self, repo_id: str, config: Config):
        self.repo_id = repo_id
        self.config = config
        self.repo = self.config.git.get_repo(self.repo_id)
        self.stats = CommitStats()
        self.filtered_commits: list[str] = []

        since = self.config.commits_dict['since']
        until = self.config.commits_dict['until']

        try:
            if self.config.sha:
                self.commits = self.repo.get_commits(sha=self.config.sha) 
            else:
                self.commits = self.repo.get_commits(sha=self.repo.default_branch, since=since, until=until)
        except Exception as e:
            logging.exception(f"[{self.repo.full_name}] Error fetching commits: {e}")
            self.commits = []
        

    def get_commits(self) -> None:
        if not self.commits:
            logging.warning(f"[{self.repo.full_name}] No commits found")
            return
        
        for commit in tqdm(self.commits, desc=f"{self.repo.full_name} commits"):
            try:
                self.stats.num_commits += 1
                if not CommitFilter(commit, self.config, self.repo).accept():
                    continue
                
                writer = Writer(self.repo.full_name, self.config.output or self.config.storage['commits'])
                self.filtered_commits.append(writer.file or "")
                self.stats.perf_commits += 1
                self.stats += writer.write_commit(commit, self.config.separate)

            except Exception as e:
                logging.exception(f"[{self.repo.full_name}] Error processing commit: {e}")

        self.stats.write_final_log()


class CommitTesterPipeline:
    def __init__(self, config: Config):
        self.config = config 
        self.tester = CommitTester(self.config.output or self.config.storage['commits'])    

    def test_commit(self) -> None:
        if self.config.sha:
            commits = self.config.git.search_commits(f"hash:{self.config.sha}")
            for commit in commits:
                repo = commit.repository
                if not repo.fork:
                    file = "_".join(repo.full_name.split("/"))
                    commit = repo.get_commit(self.config.sha)
                    new_sha = self.config.sha
                    if not commit.parents:
                        logging.info(f"[{repo.full_name}] Commit {self.config.sha} has no parents (root commit).")
                        return
                    old_sha = commit.parents[0].sha
                    new_path, old_path = self.tester.get_paths(file, new_sha)
                    self._run_commit_pair(repo.full_name, new_sha, old_sha, new_path, old_path)
                    break
            
        elif self.config.newsha and self.config.oldsha:
            commits = self.config.git.search_commits(f"hash:{self.config.newsha}")
            for commit in commits:
                repo = commit.repository
                if not repo.fork:
                    file = "_".join(repo.full_name.split("/"))
                    new_sha = self.config.newsha
                    old_sha = self.config.oldsha
                    new_path, old_path = self.tester.get_paths(file, new_sha)
                    self._run_commit_pair(repo.full_name, new_sha, old_sha, new_path, old_path)
                    break
        else:
            self._tester()

    def _tester(self) -> None:
        crawler = RepositoryCrawler(self.config)
        repos = crawler.get_repos()  
        if not repos:
            logging.warning("No repositories found for commit testing.")
            return
        
        for repo in tqdm(repos, total=len(repos), desc=f"Testing..."):
            try: 
                commits, file = self.tester.get_commits(repo)
                for (new_sha, old_sha) in tqdm(commits, total=len(commits), desc=f"Testing filtered commits..."):
                    try:
                        new_path, old_path = self.tester.get_paths(file, new_sha)
                        self._run_commit_pair(repo, new_sha, old_sha, new_path, old_path)
                        """
                        with self._commit_pair_test(repo, self.config, new_path, old_path, new_sha, old_sha) as (new_times, old_times, new_struct, old_struct):
                            logging.info(f"Times Old: {old_times}, New: {new_times}")
                            warmup = self.config.testing['warmup']
                            if self._is_exec_time_improvement_significant(new_times[warmup:], old_times[warmup:]):
                                if old_struct and old_struct.process:
                                    old_struct.process.save_docker_image(repo, new_sha)
                                logging.info(f"[{repo}] ({new_sha}) significantly improves the execution time.")
                                Writer(repo, self.config.output or self.config.storage['performance']).write_improve(new_sha, old_sha)
                        """
                    except Exception as e:
                        logging.exception(f"[{repo}] Error testing commits: {e}")

            except Exception as e:
                logging.exception(f"[{repo}] Error testing repository: {e}")

    def _run_commit_pair(
        self,
        repo: str,
        new_sha: str,
        old_sha: str,
        new_path: Path,
        old_path: Path,
    ) -> None:
        try:
            with self._commit_pair_test(
                repo, self.config, new_path, old_path, new_sha, old_sha
            ) as (new_times, old_times, new_struct, old_struct):
                logging.info(f"Times Old: {old_times}, New: {new_times}")
                warmup = self.config.testing["warmup"]

                if self._is_exec_time_improvement_significant(new_times[warmup:], old_times[warmup:]):
                    if old_struct and old_struct.process:
                        old_struct.process.save_docker_image(repo, new_sha)

                    logging.info(f"[{repo}] ({new_sha}) significantly improves execution time.")
                    Writer(repo, self.config.output or self.config.storage["performance"]).write_improve(new_sha, old_sha)

        except Exception as e:
            logging.exception(f"[{repo}] Error running commit pair test: {e}")

    def _is_exec_time_improvement_significant(
        self,
        v1_times: list[float],
        v2_times: list[float]
    ) -> bool:
        if len(v1_times) != len(v2_times):
            raise ValueError("v1_times and v2_times must have the same length")
        v1 = np.asarray(v1_times, dtype=float)
        v2 = np.asarray(v2_times, dtype=float)

        c = 1.0 - self.config.commits_dict['min-exec-time-improvement']  # we test μ1 < c * μ2
        v2_scaled = c * v2

        # Welch's t-test, one-sided: H1: mean(v1) < mean(v2_scaled)
        res = stats.ttest_ind(v1, v2_scaled, equal_var=False, alternative='less')
        logging.info(f"T-test result: {res.statistic} (statistic), {res.pvalue} (pvalue)") # type: ignore
        return bool(res.pvalue < self.config.commits_dict['min-p-value']) # type: ignore

    @contextmanager
    def _commit_pair_test(
        self, 
        repo: str, 
        config: Config, 
        new_path: Path, 
        old_path: Path, 
        new_sha: str, 
        old_sha: str
    ) -> Generator[tuple[list[float], list[float], Optional[StructureFilter], Optional[StructureFilter]], Any, Any]:
        """
        Start a container for new/old commits and stop container automatically after both runs.
        """
        new_pf = ProcessFilter(repo, config, new_path, new_sha)
        old_pf = ProcessFilter(repo, config, old_path, old_sha)
        docker_image = ""
        
        try:
            new_times, new_structure = new_pf.valid_commit_run("New", container_name=new_sha)
            docker_image = new_structure.process.docker_image if new_structure and new_structure.process else ""
            
            old_times, old_structure = old_pf.valid_commit_run("Old", container_name=new_sha, docker_image=docker_image)
            
            yield new_times, old_times, new_structure, old_structure
            
        finally:
            for struct in [new_structure, old_structure]:
                try:
                    if struct and struct.process:
                        struct.process.docker.stop_container()
                        break
                except Exception as e:
                    logging.warning(f"[{repo}] Failed to stop container: {e}")