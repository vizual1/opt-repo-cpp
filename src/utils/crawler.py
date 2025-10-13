import os, logging, time
from datetime import datetime, timezone
from tqdm import tqdm
import src.config as conf
from src.utils.dataclasses import Config

class RepositoryCrawler:
    def __init__(self, config: Config, url: str = "", type: str = "C++"):
        self.url = url
        self.type = type
        self.config = config
        self.storage: dict[str, str] = conf.storage

    def get_repos(self) -> list[str]:
        if self.config.popular:
            repos = self._query_popular_repos()
            os.makedirs("data", exist_ok=True)
            with open("data/popular_urls.txt", "w", encoding="utf-8") as f:
                for repo in repos:
                    f.write(f"https://github.com/{repo}\n")
            return repos
        else:
            if self.config.read:
                path = self.config.read
            else:
                path = self.storage['repo_urls']
            return self._get_repo_ids(path, self.url)
    
    def _query_popular_repos(self) -> list[str]:
        ok_language = [
            "C++", "CMake", "Shell", "C", "Makefile", "Dockerfile",
            "Meson", "Bazel", "Ninja", "QMake", "Gradle", "JSON", "YAML",
            "TOML", "INI", "Batchfile", "PowerSHell", "Markdown",
            "HTML", "CSS", "TeX"
        ]
        result = []
        count = 0

        upper = self.config.stars 
        lower = upper

        pbar = tqdm(desc="Getting popular repos...")

        while lower > -1 and count < self.config.limit:
            upper = lower
            lower = int(0.95 * upper)

            query = f"language:{self.type} stars:{lower}..{upper}"
            logging.info(f"Querying popular repos ({query})...")
            repos = self.config.git.search_repositories(query=query, sort="stars", order="desc")

            for repo in repos:
                languages = repo.get_languages() 
                cpp = languages.get("C++", 0)
                total_bytes = sum(languages.values())
                #cmake = languages.get("CMake", 0)

                if total_bytes == 0:
                    continue

                others_ok = all((size / total_bytes) <= 0.05 for lang, size in languages.items() if lang not in ok_language)
                if cpp > 0 and others_ok:
                    result.append(repo.full_name)
                    count += 1
                
                pbar.update(1)
                pbar.set_postfix({"matched": count})

                if count >= self.config.limit:
                    break

                time.sleep(0.5)

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
            for url in urls:
                repo_ids.append(url.removeprefix("https://github.com/").strip())
        except (OSError, IOError) as e:
            logging.error(f"Failed to read {path}: {e}", exc_info=True)

        return repo_ids
    