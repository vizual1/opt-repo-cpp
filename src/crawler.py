import os, logging, tempfile
from tqdm import tqdm
from github import Github, Auth
from github.Commit import Commit
from src.utils.filter import *
from src.utils.commit import *
from src.cmake.analyzer import CMakeAnalyzer
from src.utils.statistics import CrawlStats
from src.llm.openai import OpenRouterLLM
import src.config as conf

class GithubCrawler(CrawlStats):
    def __init__(self, 
                 url: str = "", # select a specific repo
                 filter: str = "simple", 
                 sha: str = "", # select a specific commit version 
                 separate: bool = False, # saves each commit with msg and patch separately
                 popular: bool = False, # get popular repositories directly from GitHub
                 type: str = "C++",
                 stars: int = 1000, 
                 limit: int = 1
                 ):
        
        super().__init__()
        access_token: str = conf.github['access_token']
        auth = Auth.Token(access_token)
        self.git = Github(auth=auth)
        self.storage: dict[str, str] = conf.storage
        self.llm = OpenRouterLLM(conf.llm['model'])
        self.cache = {}

        self.url = url
        self.filter = filter
        self.sha = sha
        self.separate = separate
        self.popular = popular
        self.type = type
        self.stars = stars
        self.limit = limit

    def _get_popular_repos(self) -> list[dict[str, str]]:
        query = f"language:{self.type} stars:>={self.stars}"
        repos = self.git.search_repositories(query=query, sort="stars", order="desc")

        result = []
        for repo in repos[:self.limit]: 
            result.append({"name": repo.full_name, "url": repo.html_url}) # type: ignore
        return result

    def crawl(self) -> None:
        if self.popular:
            logging.info(f"Get popular repos for {self.type} with more than {self.stars} stars...")
            repos = self._get_popular_repos()
            logging.info(f"Popular repos found: {repos}")
            for repo in repos:
                self._fetch_commit_history(repo['name'])
        elif not self.sha:
            self._crawl_repolist()
        else:
            self._fetch_commit_sha(get_repo_ids("", self.url)[0])

    def _crawl_repolist(self) -> None:
        """
        Iterates through a list of GitHub repositories and fetches commit histories for each.
        """
        repo_ids: list[str] = get_repo_ids(os.path.join(self.storage['repo_urls']), self.url)

        logging.info(f"Fetching commit history...")
        for repo_id in repo_ids:
            self._fetch_commit_history(repo_id)

    def _fetch_commit_sha(self, repo_id: str) -> None:
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
        cmake_files = get_repo_tree(repo)

        if has_root_cmake(cmake_files):
            with tempfile.TemporaryDirectory() as tmpdir:
                cmakelists = get_cmakelists(repo, cmake_files, tmpdir)
                analyzer = CMakeAnalyzer(tmpdir)

                """
                # TODO: do tests to check if "include(CTest)" or "BUILD_TESTING" flag exists 
                if analyzer.has_build_testing_flag():
                    logging.info(f"BUILD_TESTING in GitHub repository {repo.full_name}.")
                    if analyzer.has_ctest():
                        logging.info(f"include(CTest) in GitHub repository {repo.full_name}.")
                """
                if analyzer.has_testing():
                    logging.info(f"Fetching and filtering commits of {repo.full_name} ...")
                    # TODO: maybe do binary search first for root CMake and CTest and maybe also test/ folder?
                    for commit in tqdm(commits, total=commits.totalCount, desc=f"{repo.full_name} commits"):
                        self._filter_and_store_commit(commit, owner, name)
                        self.num_commits += 1
                    self.write_final_log()
                else:
                    logging.info(f"No CMake or CTest found in GitHub repository {repo.full_name}.")
                
        else:
            logging.info(f"No CMake at root found in GitHub repository {repo.full_name}.")

    def _filter(self, commit: Commit, repo_name: str) -> bool:
        if self.filter == "simple":
            return simple_filter(commit) and test_filter(commit) and cpp_filter(commit)
        elif self.filter == "llm":
            return llm_filter(self.llm, repo_name, commit) and test_filter(commit) and cpp_filter(commit)
        return True

    def _filter_and_store_commit(self, commit: Commit, owner: str, name: str) -> None:
        """
        Filters a single GitHub commit, applies a filter to its message and files, 
        and writes filtered commit info to a txt file.

        Args:
            commit: A PyGithub Commit object representing a single commit.
            owner (str): GitHub repository owner.
            name (str): GitHub repository name.
        """
        current_sha = commit.sha
        #if not self._load_cache(current_sha) and 
        if self._filter(commit, f"{owner}/{name}"):
            self.perf_commits += 1
            
            if commit.parents:
                parent_sha = commit.parents[0].sha
            else:
                parent_sha = None 

            total_add = sum(f.additions for f in commit.files)
            total_del = sum(f.deletions for f in commit.files)

            self.lines_added += total_add
            self.lines_deleted += total_del

            file = f"{owner}_{name}_filtered.txt"
            msg = f"{current_sha} | {commit.parents[0].sha or 'None'} | +{total_add} | -{total_del} | {total_add + total_del}" 
            write_commits(os.path.join(self.storage['dataset'], file), msg)
            self._save_cache(commit)
            
            if self.separate:
                file = f"{owner}_{name}_{current_sha}.txt"
                msg = f"{current_sha} | {commit.parents[0].sha or 'None'} \n {commit.commit.message} \n"
                for f in commit.files:
                    msg += f"{f.patch} \n"
                write_commits(os.path.join(self.storage['dataset'], file), msg)

    # TODO: write save_cache/load_cache and test it
    def _save_cache(self, commit: Commit) -> None:
        self.cache[commit.sha] = {} # TODO: add commit information to cache
        # TODO: write the cache to memory
        return
    
    def _load_cache(self, sha: str) -> str:
        if not self.cache:
            self.cache = {} # TODO: load the cache from outside
        elif sha in self.cache.keys():
            return self.cache[sha]
        return ""


           

