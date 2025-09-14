import os, logging, tempfile
from github import Github, Auth
from github.Commit import Commit
from src.filter import *
from src.utils.commit import *
from src.utils.cmake_parser import *
from src.utils.cmake_adapter import CMakeAdapter
from src.utils.statistics import Statistics
from src.llm.openai import OpenRouterLLM
import src.config as conf

class GithubCrawler(Statistics):
    def __init__(self, url: str = "", sha: str = "", separate: bool = False):
        super().__init__()
        access_token: str = conf.github['access_token']
        auth = Auth.Token(access_token)
        self.git = Github(auth=auth)
        self.storage: dict[str, str] = conf.storage
        self.llm = OpenRouterLLM(conf.llm['model'])
        
        self.url = url
        self.sha = sha
        self.separate = separate

    def get_popular_repos(self):
        return 0

    def crawl(self):
        """
        Iterates through a list of GitHub repositories and fetches commit histories for each.
        """
        if not self.sha:
            self.crawl_repos()
        else:
            self._fetch_commit(get_repo_ids("", self.url)[0])

    def crawl_repos(self):
        """
        Iterates through a list of GitHub repositories and fetches commit histories for each.
        """
        repo_ids = get_repo_ids(os.path.join(self.storage['repo_urls']), self.url)

        logging.info(f"Fetching commit history...")
        for repo_id in repo_ids:
            self._fetch_commit_history(repo_id)

    def _fetch_commit(self, repo_id: str):
        """
        Fetches and stores the commit sha of a GitHub repository.
        """
        repo = self.git.get_repo(repo_id)
        owner, name = repo.full_name.split("/")
        commit = repo.get_commits(self.sha)[0]

        current_sha = f"{commit.sha}"
        if commit.parents:
            parent_sha = f"{commit.parents[0].sha}"
        else:
            parent_sha = None 

        write_commits(os.path.join(self.storage['dataset'], f"{owner}_{name}_{self.sha}.txt"),
                        f"{current_sha} | {commit.parents[0].sha or 'None'} \n {commit.commit.message} \n {commit.files[0].patch}")

    def _fetch_commit_history(self, repo_id: str):
        """
        Fetches the full commit history of a GitHub repository if CMake and CTest are defined and applies a filter to each commit message.

        Args:
            repo_id (str): GitHub repository identifier in the form 'owner/repo'.
        """
        repo = self.git.get_repo(repo_id)
        owner, name = repo.full_name.split("/")
        commits = repo.get_commits()

        # TODO: more efficient by just extracting CMakeLists.txt and checking
        # TODO: check if CMakeLists.txt is in the topmost folder, if not ignore
        # GET /repos/{owner}/{repo}/git/trees/{commit_sha}?recursive=1
        repo_url = f"https://api.github.com/repos/{owner}/{name}/zipball/HEAD"
        with tempfile.TemporaryDirectory() as tmpdir:
            get_commit(repo_url, tmpdir)
            adapter = CMakeAdapter(tmpdir)

            if adapter.has_enable_testing():
                logging.info(f"Fetching and filtering commits of {owner}/{name} ...")
                for commit in commits:
                    self._filter_and_store_commit(commit, owner, name)
                    self.num_commits += 1
                self.write_final_log()
            else:
                logging.info(f"No CMake or CTest found in GitHub repository {repo.full_name}.")


    def _filter_and_store_commit(self, commit: Commit, owner: str, name: str):
        """
        Processes a single GitHub commit, applies a filter to its message, and writes filtered commit info to a txt file.

        Args:
            commit: A PyGithub Commit object representing a single commit.
            owner (str): GitHub repository owner.
            name (str): GitHub repository name.
        """
        # TODO: add additional filter: if no update to C++ files then ignore?
        # TODO: documentation-only/white-space refactoring/etc: also ignore?
        # TODO: add caching to save current_sha
        if simple_filter(commit): #if llm_filter(self.llm, f"{owner}/{name}", commit):
            self.perf_commits += 1
            current_sha = f"{commit.sha}"
            if commit.parents:
                parent_sha = f"{commit.parents[0].sha}"
            else:
                parent_sha = None 

            total_add = sum(f.additions for f in commit.files)
            total_del = sum(f.deletions for f in commit.files)

            self.lines_added += total_add
            self.lines_deleted += total_del

            file = f"{owner}_{name}_filtered.txt"
            msg = f"{current_sha} | {commit.parents[0].sha or 'None'} | +{total_add} | -{total_del} | {total_add + total_del}" 
            write_commits(os.path.join(self.storage['dataset'], file), msg)
            if self.separate:
                file = f"{owner}_{name}_{current_sha}.txt"
                msg = f"{current_sha} | {commit.parents[0].sha or 'None'} \n {commit.commit.message} \n"
                for f in commit.files:
                    msg += f"{f.patch} \n"
                write_commits(os.path.join(self.storage['dataset'], file), msg)




           

