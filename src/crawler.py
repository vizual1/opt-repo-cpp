import os, logging, tempfile
from github import Github, Auth
from github.Commit import Commit
from src.filter import *
from src.utils.commit import *
from src.utils.cmake_parser import *
from src.utils.cmake_adapter import CMakeAdapter
from src.llm.openai import OpenRouterLLM
import src.config as conf

class GithubCrawler:
    def __init__(self, url: str = "", sha: str = "", separate: bool = False):
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

        logging.info("Fetching commit history...")
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

        repo_url = f"https://api.github.com/repos/{owner}/{name}/zipball/HEAD"
        with tempfile.TemporaryDirectory() as tmpdir:
            get_commit(repo_url, tmpdir)
            adapter = CMakeAdapter(tmpdir)

            #if check_cmake_in_commit(repo):
            if adapter.has_ctest():
                logging.info(f"Fetching and filtering commits of {owner}/{name} ...")
                for commit in commits:
                    self._filter_and_store_commit(commit, owner, name)
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
        if simple_filter(commit): #if llm_filter(self.llm, f"{owner}/{name}", commit):
            current_sha = f"{commit.sha}"
            if commit.parents:
                parent_sha = f"{commit.parents[0].sha}"
            else:
                parent_sha = None 

            file = f"{owner}_{name}_filtered.txt" if not self.separate else f"{owner}_{name}_{current_sha}.txt"
            msg = f"{current_sha} | {commit.parents[0].sha or 'None'}" if not self.separate else f"{current_sha} | {commit.parents[0].sha or 'None'} \n {commit.commit.message} \n {commit.files[0].patch}"
            write_commits(os.path.join(self.storage['dataset'], file), msg)

            # TODO: get and save the commit details 
            '''
            # better: parser to calculate rewrite and store the DIFF? 
                # commit.files[0].patch (.status, .filename, etc.)
            # get the commit details => another API request 
            commit_details = repo.get_commit(sha)
            for file in commit_details.files:
                print(f" - {file.filename}, +{file.additions}/-{file.deletions}")
                if file.patch:
                    print(file.patch[:300])
            print("-" * 60)
            '''



           

