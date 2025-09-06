import os, logging
from github import Github, Auth
from github.Commit import Commit
from src.filter import simple_filter
from src.utils.crawler_utils import extract_repo_ids, write_commits
import src.config as conf

class GithubCrawler:
    def __init__(self):
        access_token: str = conf.github['access_token']
        auth = Auth.Token(access_token)
        self.git = Github(auth=auth)
        self.storage: dict[str, str] = conf.storage

    def crawl_repos(self, url: str = ""):
        """
        Iterates through a list of GitHub repositories and fetches commit histories for each.
        """
        repo_ids = extract_repo_ids(os.path.join(self.storage['repo_urls']), url)

        logging.info("Fetching commit history...")
        for repo_id in repo_ids:
            self.fetch_commit_history(repo_id)

    def fetch_commit_history(self, repo_id: str):
        """
        Fetches the full commit history of a GitHub repository and applies a filter to each commit message.

        Args:
            repo_id (str): GitHub repository identifier in the form 'owner/repo'.
        """
        repo = self.git.get_repo(repo_id)
        owner, name = repo.full_name.split("/")
        os.makedirs(os.path.join(self.storage['dataset'], f"{owner}_{name}"), exist_ok=True)
        commits = repo.get_commits()

        for commit in commits:
            self.filter_and_store_commit(commit, owner, name)


    def filter_and_store_commit(self, commit: Commit, owner: str, name: str):
        """
        Processes a single GitHub commit, applies a filter to its message, and writes filtered commit info to a txt file.

        Args:
            commit: A PyGithub Commit object representing a single commit.
            owner (str): GitHub repository owner.
            name (str): GitHub repository name.
        """
        msg = " ".join(commit.commit.message.split())
        current_sha = f"{commit.sha}"
        likelihood = simple_filter(msg) # TODO: add LLM filter

        # TODO: add likelihood and logging message
        if likelihood >= conf.likelihood['min_likelihood']:
            date = f"{commit.commit.author.date}"
            if commit.parents:
                parent_sha = f"{commit.parents[0].sha}"
            else:
                parent_sha = None 

            write_commits(os.path.join(self.storage['dataset'], f"{owner}_{name}", self.storage['filtered']),
                            f"{date} | {current_sha} | {parent_sha or 'None'} | {msg}")

            logging.info(f"{owner}/{name} - Commit {current_sha}: likelihood {likelihood}%")
            # TODO: maybe get and save the commit details 
            '''
            # get the commit details 
            commit_details = repo.get_commit(sha)
            for file in commit_details.files:
                print(f" - {file.filename}, +{file.additions}/-{file.deletions}")
                if file.patch:
                    print(file.patch[:300])
            print("-" * 60)
            '''
        elif likelihood < conf.likelihood['max_likelihood']:
            assert True
        else:
            assert True

           

