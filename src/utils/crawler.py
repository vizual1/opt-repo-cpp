import os, logging, time
from tqdm import tqdm
import src.config as conf
from src.utils.dataclasses import Config
from github.GithubException import GithubException, RateLimitExceededException

class RepositoryCrawler:
    def __init__(self, config: Config, url: str = "", language: str = "C++"):
        self.url = url
        self.language = language
        self.config = config
        self.storage: dict[str, str] = conf.storage
        self.popular_file = self.storage["popular"]

    def get_repos(self) -> list[str]:
        if self.config.popular:
            repos = self._query_popular_repos()
            self._write_popular_urls(repos)
            return repos

        path = self.config.read or self.storage.get("repo_urls", "")
        return self._get_repo_ids(path, self.url)
    
    def _query_popular_repos(self) -> list[str]:
        ok_language = [
            "C++", "CMake", "Shell", "C", "Makefile", "Dockerfile",
            "Meson", "Bazel", "Ninja", "QMake", "Gradle", "JSON", "YAML",
            "TOML", "INI", "Batchfile", "PowerSHell", "Markdown",
            "HTML", "CSS", "TeX"
        ]

        results: list[str] = []
        upper = self.config.stars 
        lower = upper
        limit = self.config.limit
        count = 0

        logging.info(f"Starting GitHub query for popular {self.language} repos...")

        pbar = tqdm(desc="Getting popular repos...")
        while lower > -1 and count < self.config.limit:
            upper = lower
            lower = int(0.95 * upper)
            query = f"language:{self.language} stars:{lower}..{upper}"

            logging.info(f"Query: {query}")

            try:
                repos = self.config.git.search_repositories(query=query, sort="stars", order="desc")
                for repo in repos:
                    try:
                        languages = repo.get_languages() 
                        cpp = languages.get("C++", 0)
                        total_bytes = sum(languages.values())
                        #cmake = languages.get("CMake", 0)

                        if total_bytes == 0:
                            continue

                        others_ok = all((size / total_bytes) <= 0.05 for lang, size in languages.items() if lang not in ok_language)
                        if cpp > 0 and others_ok:
                            results.append(repo.full_name)
                            count += 1
                    
                        pbar.update(1)
                        pbar.set_postfix({"matched": count})

                        if count >= limit:
                            break

                        time.sleep(0.5)

                    except GithubException as e:
                        logging.warning(f"Skipping repo due to GitHub error: {e}")
                        continue

            except RateLimitExceededException:
                logging.warning("Rate limit exceeded. Waiting 60 seconds...")
                time.sleep(60)
            except GithubException as e:
                logging.error(f"GitHub API error: {e}")
                time.sleep(5)
                continue
        
        logging.info(f"Collected {len(results)} popular repositories.")
        return results
    
    def _get_repo_ids(self, path: str, url: str = "") -> list[str]:
        """Extract repository IDs (owner/repo) from GitHub URLs."""
        repo_ids: list[str] = []

        if url:
            repo_ids.append(url.removeprefix("https://github.com/").strip())
            return repo_ids
        
        try:
            with open(path, 'r', errors='ignore') as f:
                lines = f.readlines()
            print("TEST1")
            for line in lines:
                line = line.strip()
                if not line or not line.startswith("https://github.com/"):
                    continue
                repo_ids.append(line.removeprefix("https://github.com/").strip())

            logging.info(f"Loaded {len(repo_ids)} repository URLs from {path}")

        except (OSError, IOError) as e:
            logging.error(f"Failed to read repo list from {path}: {e}", exc_info=True)

        return repo_ids
    
    def _write_popular_urls(self, repos: list[str]) -> None:
        """Write fetched repository URLs to file."""
        try:
            with open(self.popular_file, "w", encoding="utf-8") as f:
                for repo in repos:
                    f.write(f"https://github.com/{repo}\n")
            logging.info(f"Popular repos written to {self.popular_file}")
        except (OSError, IOError) as e:
            logging.error(f"Failed to write {self.popular_file}: {e}", exc_info=True)
