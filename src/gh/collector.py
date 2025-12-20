import logging, time
from tqdm import tqdm
from datetime import datetime, timezone, timedelta
from pathlib import Path
from src.config.config import Config
from github.GithubException import GithubException, RateLimitExceededException
from github.Repository import Repository

class RepositoryCollector:

    # languages considered acceptable alongside C++
    ACCEPTABLE_LANGUAGES = {
        "C++", "CMake", "Shell", "C", "Makefile", "Dockerfile",
        "Meson", "Bazel", "Ninja", "QMake", "Gradle", "JSON", "YAML",
        "TOML", "INI", "Batchfile", "PowerShell", "Markdown",
        "HTML", "CSS", "TeX"
    }
    MAX_OTHER_LANGUAGE_RATIO = 0.05
    STAR_REDUCTION_FACTOR = 0.95

    def __init__(self, config: Config, language: str = "C++"):
        self.language = language
        self.config = config

    def get_repos(self) -> list[str]:
        """Get repository IDs from input file or default location."""
        path = self.config.input_file or self.config.storage_paths["repos"]
        logging.debug(f"Loading repos from: {path}")
        return self._get_repo_ids(path)
    
    def query_popular_repos(self) -> list[Repository]:
        """
        Query GitHub for popular repositories matching criteria.
        
        Returns:
            List of Repository objects that match language and composition criteria
        """
        # TODO: test
        seen_repo_ids = set()
        if self.config.input_file:
            seen_repo_ids = set(self._get_repo_ids(self.config.input_file))
            logging.info(f"Loaded {len(seen_repo_ids)} existing repositories to skip")

        results: list[Repository] = []
        #upper = self.config.stars 
        #lower = upper
        limit = self.config.limit
        count = 0

        logging.info(f"Starting GitHub query for popular {self.language} repos...")
        logging.info(f"Target: {limit} repos") #with stars <= {upper}")

        start_boundary = self.config.commits_time['since'] #datetime.strptime(, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        window_end = datetime.now(timezone.utc)
        window_size = timedelta(days=1)
            
        with tqdm(desc="Discovering repos", unit="repo", mininterval=5) as pbar:
            while window_end > start_boundary and count < limit:
            #while lower > 0 and count < limit:
            #    upper = lower
            #    lower = int(self.STAR_REDUCTION_FACTOR * upper)
                window_start = max(start_boundary, window_end - window_size)
                pushed_range = f"pushed:{window_start.date()}..{window_end.date()}"
                #query = f"language:{self.language} stars:{lower}..{upper}"
                query = f"{pushed_range}, language:{self.language}, archived:false,"

                if getattr(self.config, "stars", None):
                    query += f" stars:<={self.config.stars}"
                    query += f" stars:>={self.config.commits_time['min-stars']}"

                logging.info(f"Query: {query}")

                try:
                    repos = self.config.git_client.search_repositories(
                        query=query, sort="stars", order="desc"
                    )
                    for repo in repos:
                        if repo.full_name in seen_repo_ids:
                            logging.debug(f"Skipping {repo.full_name}: already in input list")
                            continue
                        
                        if self._is_valid_repo(repo):
                            results.append(repo)
                            seen_repo_ids.add(repo.full_name)
                            count += 1
                            pbar.update(1)
                            pbar.set_postfix({"matched": count})

                            if count >= limit:
                                break

                        time.sleep(0.5)

                except RateLimitExceededException:
                    logging.warning("Rate limit exceeded. Waiting 60 seconds...")
                    time.sleep(60)
                    continue
                except GithubException as e:
                    logging.error(f"GitHub API error: {e}")
                    time.sleep(5)
                    continue

                window_end = window_start
            
        logging.info(f"Collected {len(results)} repositories matching criteria")
        return results
    
    def _is_valid_repo(self, repo: Repository) -> bool:
        """
        Check if repository meets language composition criteria.
        
        Args:
            repo: GitHub Repository object to validate
            
        Returns:
            True if repo has C++ and acceptable language composition
        """
        try:
            languages = repo.get_languages()
            cpp_bytes = languages.get("C++", 0)
            total_bytes = sum(languages.values())

            if total_bytes == 0 or cpp_bytes == 0:
                return False
            
            for lang, size in languages.items():
                if lang not in self.ACCEPTABLE_LANGUAGES:
                    ratio = size / total_bytes
                    if ratio > self.MAX_OTHER_LANGUAGE_RATIO:
                        logging.debug(
                            f"Rejecting {repo.full_name}: "
                            f"{lang} comprises {ratio:.1%} (threshold: {self.MAX_OTHER_LANGUAGE_RATIO:.1%})"
                        )
                        return False
            
            return True

        except GithubException as e:
            logging.warning(f"Error checking languages for {repo.full_name}: {e}")
            return False
    
    def _get_repo_ids(self, path: str) -> list[str]:
        """
        Extract repository IDs (owner/repo) from file or URL.
        
        Supports multiple formats:
        - GitHub URLs: https://github.com/owner/repo
        - Direct format: owner/repo
        - CSV format: owner/repo,other,data
        - Pipe-delimited tables
        
        Args:
            path: File path or URL to parse
            
        Returns:
            List of repository IDs in 'owner/repo' format
        """
        repo_ids: list[str] = []

        if self.config.repo_id:
            repo_id = self.config.repo_id
            repo_ids.append(repo_id)
            logging.info(f"Using single repository from URL: {repo_id}")
            return repo_ids
        
        try:
            file_path = Path(path)
            if not file_path.exists():
                logging.warning(f"Input file not found: {path}")
                return repo_ids
            
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                line = line.strip()

                if not line:
                    continue

                try:
                    repo_id = self._parse_repo_line(line, path)
                    if repo_id:
                        repo_ids.append(repo_id)
                except Exception as e:
                    logging.warning(f"Error parsing line {i} in {path}: {e}")
                    continue

            logging.info(f"Loaded {len(repo_ids)} repository URLs from {path}")

        except (OSError, IOError) as e:
            logging.error(f"Failed to read repo list from {path}: {e}", exc_info=True)

        return repo_ids
    
    def _parse_repo_line(self, line: str, filepath: str) -> str:
        """
        Parse a single line to extract repository ID.
        
        Args:
            line: Line to parse
            filepath: Source file path (used for pipe-delimited format)
            
        Returns:
            Repository ID in 'owner/repo' format, or None if invalid
        """
        # Pipe-delimited table format (extract from filename)
        if '|' in line:
            # Extract owner/repo from filename pattern
            filename = Path(filepath).stem
            parts = filename.split('_')
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
            return ""
        
        # CSV format
        if ',' in line:
            repo_url = line.split(',')[0].strip()
            return repo_url.removeprefix("https://github.com/").strip()
        
        # Direct format or URL
        return line.removeprefix("https://github.com/").strip()