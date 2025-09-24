import os, logging
from tqdm import tqdm
from github import Github, Auth
import src.config as conf
from src.utils.helper import get_repo_ids

class RepositoryCrawler:
    def __init__(self, url: str = "", popular: bool = False, 
                 type: str = "C++", stars: int = 1000, limit: int = 10):
        self.url = url
        self.popular = popular
        self.type = type
        self.stars = stars
        self.limit = limit

        access_token: str = conf.github['access_token']
        auth = Auth.Token(access_token)
        self.git = Github(auth=auth)
        rate_limit = self.git.get_rate_limit()
        logging.info(f"GitHub rate limit rate: {rate_limit.rate}")

        self.storage: dict[str, str] = conf.storage

    def _query_popular_repos(self) -> list[str]:
        query = f"language:{self.type} stars:>={self.stars}"

        logging.info(f"Get popular repos for {self.type} with more than {self.stars} stars...")
        repos = self.git.search_repositories(query=query, sort="stars", order="desc")

        result = []
        count = 0
        for repo in tqdm(repos, total=self.limit, desc=f"Getting popular repos for {self.type} with more than {self.stars}..."):
            result.append(repo.full_name) # type: ignore
            count += 1
            if count >= self.limit:
                break

        return result
    
    def get_repos(self) -> list[str]:
        if self.popular:
            return self._query_popular_repos()
        else:
            return get_repo_ids(os.path.join(self.storage['repo_urls']), self.url)