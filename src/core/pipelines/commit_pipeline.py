import logging, ast
from tqdm import tqdm
from src.config.config import Config
from src.utils.writer import Writer
from src.core.filter.commit_filter import CommitFilter
from src.utils.stats import CommitStats
from github.Repository import Repository
from github.Commit import Commit
from pathlib import Path

class CommitPipeline:
    """
    This class filters and saves the commit history of a repository.
    """
    def __init__(self, repo_ids: list[str], config: Config):
        self.config = config
        self.repo_ids = repo_ids
        self.stats = CommitStats()
        self.filtered_commits: list[Commit] = []

    def filter_all_commits(self):
        if self.config.sha and self.config.repo_id:
            repo = self.config.git_client.get_repo(self.config.repo_id)
            try:
                self.commits = [repo.get_commit(sha=self.config.sha)]
            except Exception as e:
                logging.exception(f"[{repo.full_name}] Error fetching commits: {e}")
                self.commits = []
            self.filter_commits_from_repo(repo)
            return
        
        for repo_id in self.repo_ids:
            repo = self.config.git_client.get_repo(repo_id)

            since = self.config.commits_time['since']
            until = self.config.commits_time['until']
            try:
                self.commits = repo.get_commits(sha=repo.default_branch, since=since, until=until)
            except Exception as e:
                logging.exception(f"[{repo.full_name}] Error fetching commits: {e}")
                self.commits = []
            self.filter_commits_from_repo(repo)

    def filter_commits_from_repo(self, repo: Repository) -> None:
        if not self.commits:
            logging.warning(f"[{repo.full_name}] No commits found")
            return
        
        stats = CommitStats()
        filtered_commits: list[str] = []
        for commit in tqdm(self.commits, desc=f"{repo.full_name} commits", position=1, leave=False, mininterval=5):
            stats.num_commits += 1
            perf_improv_filter = CommitFilter(repo, commit, self.config)
            if not perf_improv_filter.accept():
                continue
            
            self.filtered_commits.append(commit)
            writer = Writer(repo.full_name, self.config.output_file or self.config.storage_paths['commits'])
            filtered_commits.append(writer.file or "")
            stats.perf_commits += 1
            stats += writer.write_pr_commit(repo, commit, perf_improv_filter.is_issue)

        self._rewrite_commits()
        stats.write_final_log()

    def filter_commits(self, repo: Repository, commits: list[Commit]) -> None:
        if not commits:
            logging.warning(f"[{repo.full_name}] No commits found")
            return
        
        stats = CommitStats()
        filtered_commits: list[str] = []
        for commit in tqdm(commits, desc=f"{repo.full_name} commits", position=1, leave=False, mininterval=5):
            stats.num_commits += 1
            perf_improv_filter = CommitFilter(repo, commit, self.config)
            if not perf_improv_filter.accept():
                continue
            
            self.filtered_commits.append(commit)
            writer = Writer(repo.full_name, self.config.output_file or self.config.storage_paths['clones'])
            filtered_commits.append(writer.file or "")
            stats.perf_commits += 1
            stats += writer.write_pr_commit(repo, commit, perf_improv_filter.is_issue)

        self._rewrite_commits()
        stats.write_final_log()


    def _read_commits(self) -> list[str]:
        """
        Merges multiple 'owner/repo | patched_sha | original_sha | new_shaN' into 
        'owner/repo | patched_sha | original_sha | [new_sha1, ..., new_shaN]'
        """
        commits: dict[str, list[str]] = {}
        path = self.config.output_file or self.config.storage_paths['clones']
        file = "filtered.txt"
        path = Path(path) / file
        with open(path, "r") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) <= 2:
                    logging.warning(f"Malformed commit line at {path}:{line_no} -> {line}")
                    continue
                msg = f"{parts[0]} | {parts[1]} | {parts[2]}"
                
                if len(parts) > 3:
                    # repo_id | new_sha | old_sha | new_sha_not_pr
                    extra_commits = ast.literal_eval(parts[3])
                    commits.setdefault(msg, []).extend(extra_commits)
                    continue
                
                commits.setdefault(msg, [])
                    
        output = [f"{k} | {v}" for k, v in commits.items()]
        return output
    
    def _organize_commits(self) -> list[str]:
        commits = self._read_commits()
        commits = list(set(commits))
        commits.sort(key=str.casefold)
        return commits
    
    def _rewrite_commits(self) -> None:
        commits = self._organize_commits()
        path = self.config.output_file or self.config.storage_paths['clones']
        file = "filtered.txt"
        path = Path(path) / file
        with open(path, "w") as f:
            for line in commits:
                f.write(line + "\n")