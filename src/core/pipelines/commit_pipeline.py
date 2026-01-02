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
    def __init__(self, repo_ids: list[str], config: Config):
        self.config = config
        self.repo_ids = repo_ids
        #self.repo = repo
        #self.repo_id = self.repo.full_name
        self.stats = CommitStats()
        self.filtered_commits: list[str] = []

    def filter_all_commits(self):
        if self.config.sha and self.config.repo_id:
            repo = self.config.git_client.get_repo(self.config.repo_id)
            try:
                self.commits = [repo.get_commit(sha=self.config.sha)]
            except Exception as e:
                logging.exception(f"[{repo.full_name}] Error fetching commits: {e}")
                self.commits = []
            self._filter_commits(repo)
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
            self._filter_commits(repo)

    def _filter_commits(self, repo: Repository) -> None:
        if not self.commits:
            logging.warning(f"[{repo.full_name}] No commits found")
            return
        
        stats = CommitStats()
        filtered_commits: list[str] = []
        for commit in tqdm(self.commits, desc=f"{repo.full_name} commits", position=1, leave=False, mininterval=5):
            stats.num_commits += 1
            try:
                if not CommitFilter(commit, self.config, repo).accept():
                    continue
            except Exception as e:
                logging.exception(f"[{repo.full_name}] Error processing commit: {e}")
                continue
            
            writer = Writer(repo.full_name, self.config.output_file or self.config.storage_paths['clones'])
            filtered_commits.append(writer.file or "")
            stats.perf_commits += 1
            stats += writer.write_commit(commit, self.config.separate, self.config.filter_type)

        # TODO: test
        self._rewrite_commits()
        stats.write_final_log()

    def _read_commits(self) -> list[str]:
        commits: list[str] = []
        with open(self.config.output_file or self.config.storage_paths['clones'], "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                commits.append(line)
        return commits
    
    def _organize_commits(self) -> list[str]:
        commits = self._read_commits()
        commits = list(set(commits))
        commits.sort(key=str.casefold)
        return commits
    
    def _rewrite_commits(self) -> None:
        commits = self._organize_commits()
        with open(self.config.output_file or self.config.storage_paths['clones'], "w") as f:
            for line in commits:
                f.write(line + "\n")