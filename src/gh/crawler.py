import logging, time
from tqdm import tqdm
from src.config.config import Config
from github.GithubException import GithubException, RateLimitExceededException
from github.Repository import Repository

class RepositoryCrawler:
    def __init__(self, config: Config, language: str = "C++"):
        self.language = language
        self.config = config

    def get_repos(self) -> list[str]:
        path = self.config.input_file or self.config.storage_paths["repos"]
        logging.debug(f"{self.config.input_file} and {path}")
        return self._get_repo_ids(path)
    
    def query_popular_repos(self) -> list[Repository]:
        ok_language = [
            "C++", "CMake", "Shell", "C", "Makefile", "Dockerfile",
            "Meson", "Bazel", "Ninja", "QMake", "Gradle", "JSON", "YAML",
            "TOML", "INI", "Batchfile", "PowerSHell", "Markdown",
            "HTML", "CSS", "TeX"
        ]

        results: list[Repository] = []
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
                repos = self.config.git_client.search_repositories(query=query, sort="stars", order="desc")
                for repo in repos:
                    try:
                        languages = repo.get_languages() 
                        cpp = languages.get("C++", 0)
                        total_bytes = sum(languages.values())

                        if total_bytes == 0:
                            continue

                        others_ok = all((size / total_bytes) <= 0.05 for lang, size in languages.items() if lang not in ok_language)
                        if cpp > 0 and others_ok:
                            results.append(repo)
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
    
    def _get_repo_ids(self, path: str) -> list[str]:
        """Extract repository IDs (owner/repo) from GitHub URLs."""
        repo_ids: list[str] = []

        if self.config.repo_url:
            repo_ids.append(self.config.repo_url.removeprefix("https://github.com/").strip())
            return repo_ids #[self.config.git_client.get_repo(r) for r in repo_ids]
        
        try:
            with open(path, 'r', errors='ignore') as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if len(line.split('|')) > 1:
                    # case if commits sha were given and extract owner/repo of the form owner_repo_filtered.txt
                    repo_ids.append("/".join(path.split('/')[-1].split('_')[0:2]))
                    break
                elif len(line.split(',')) > 1:
                    split_line = line.split(',')
                    repo_ids.append(split_line[0].removeprefix("https://github.com/").strip())
                else:
                    repo_ids.append(line.removeprefix("https://github.com/").strip())

            logging.info(f"Loaded {len(repo_ids)} repository URLs from {path}")

        except (OSError, IOError) as e:
            logging.error(f"Failed to read repo list from {path}: {e}", exc_info=True)

        return repo_ids #[self.config.git_client.get_repo(r) for r in repo_ids]
    
