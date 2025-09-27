import os, logging
from tqdm import tqdm
import src.config as conf
from src.utils.dataclasses import Config

class RepositoryCrawler:
    def __init__(self, url: str = "", type: str = "C++", config: Config = Config()):
        self.url = url
        self.type = type
        self.config = config
        self.storage: dict[str, str] = conf.storage

    def get_repos(self) -> list[str]:
        if self.config.popular:
            return self._query_popular_repos()
        else:
            return self._get_repo_ids(os.path.join(self.storage['repo_urls']), self.url)
    
    def _query_popular_repos(self) -> list[str]:
        query = f"language:{self.type} stars:>={self.config.stars}"

        logging.info(f"Get popular repos...")
        repos = self.config.git.search_repositories(query=query, sort="stars", order="desc")
        
        # TODO: improve/change the code:
        ok_language = ["C++", "CMake", "Shell", "C", "Makefile", "Dockerfile"]
        result = []
        count = 0
        for repo in tqdm(repos, desc=f"Getting popular repos..."):
            languages = repo.get_languages() 
            cpp = languages.get("C++", 0)
            total_bytes = sum(languages.values())
            cmake = languages.get("CMake", 0)
            others = sum(v for k, v in languages.items() if k not in ok_language)

            if total_bytes == 0:
                continue

            others_ok = all((size / total_bytes) <= 0.02 for lang, size in languages.items() if lang not in ok_language)
            if cpp > 0 and cmake > 0 and others_ok:
                result.append(repo.full_name)
                count += 1
            
            if count >= self.config.limit:
                break

        return result
    
    def _get_repo_ids(self, path: str, url: str = "") -> list[str]:
        """Extract repository IDs (owner/repo) from GitHub URLs."""
        repo_ids: list[str] = []

        if url:
            repo_ids.append(url.removeprefix("https://github.com/").strip())
            return repo_ids
        
        try:
            with open(path, 'r', errors='ignore') as f:
                urls = f.readlines()
        except (OSError, IOError) as e:
            logging.error(f"Failed to read {path}: {e}", exc_info=True)

        for url in urls:
            repo_ids.append(url.removeprefix("https://github.com/").strip())

        return repo_ids