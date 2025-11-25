import logging
from tqdm import tqdm
from src.config.config import Config
from src.utils.writer import Writer
from src.core.filter.commit_filter import CommitFilter
from src.utils.stats import CommitStats
from github.Repository import Repository

class CommitPipeline:
    """
    This class filters and saves the commit history of a repository.
    """
    def __init__(self, repo: Repository, config: Config):
        self.config = config
        self.repo = repo
        self.repo_id = self.repo.full_name
        self.stats = CommitStats()
        self.filtered_commits: list[str] = []

        since = self.config.commits_time['since']
        until = self.config.commits_time['until']

        try:
            if self.config.sha:
                self.commits = self.repo.get_commits(sha=self.config.sha) 
            else:
                self.commits = self.repo.get_commits(sha=self.repo.default_branch, since=since, until=until)
        except Exception as e:
            logging.exception(f"[{self.repo_id}] Error fetching commits: {e}")
            self.commits = []
        

    def filter_commits(self) -> None:
        if not self.commits:
            logging.warning(f"[{self.repo_id}] No commits found")
            return
        
        for commit in tqdm(self.commits, desc=f"{self.repo_id} commits"):
            self.stats.num_commits += 1
            try:
                if not CommitFilter(commit, self.config, self.repo).accept():
                    continue
            except Exception as e:
                logging.exception(f"[{self.repo_id}] Error processing commit: {e}")
            
            writer = Writer(self.repo_id, self.config.output_file or self.config.storage_paths['commits'])
            self.filtered_commits.append(writer.file or "")
            self.stats.perf_commits += 1
            self.stats += writer.write_commit(commit, self.config.separate, self.config.filter_type)

        self.stats.write_final_log()