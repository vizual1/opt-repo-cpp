import logging
from tqdm import tqdm
from src.config.config import Config
from src.utils.stats import RepoStats
from github.Repository import Repository
from src.gh.crawler import RepositoryCrawler
from src.core.filter.structure_filter import StructureFilter
from src.core.filter.process_filter import ProcessFilter
from src.utils.writer import Writer

class RepositoryPipeline:
    """
    This class takes a list of repositories, and tests and validates them.
    """
    def __init__(self, config: Config):
        self.config = config
        self.stats = RepoStats()
        self.valid_repos: list[Repository] = []

    def get_repos(self) -> list[Repository]:
        crawler = RepositoryCrawler(config=self.config)
        return crawler.get_repos()

    def test_repos(self) -> None:
        crawler = RepositoryCrawler(self.config)
        repos = crawler.get_repos()
        if not repos:
            logging.warning("No repositories found.")
            return

        logging.info(f"Found {len(repos)} repositories.")
        for repo in tqdm(repos, total=len(repos), desc=f"Testing repositories..."):
            try:
                structure = StructureFilter(repo, self.config)
                process = ProcessFilter(repo, self.config)

                if structure.is_valid() and process.valid_run("_".join(repo.full_name.split("/"))):
                    self.valid_repos.append(structure.repo)
                    if self.config.popular or self.config.output_file:
                        #msg = [process.list_test_arg[0]] if process.list_test_arg else ["None"]
                        Writer(structure.repo.full_name, self.config.output_file).write_repo()

                elif self.config.output_file:
                    Writer(structure.repo.full_name, self.config.output_fail).write_repo()

            except Exception as e:
                logging.exception(f"[{repo}] Error processing repository: {e}")

           
    def analyze_repos(self) -> None:
        crawler = RepositoryCrawler(config=self.config)
        repos = crawler.get_repos()
        if not repos:
            logging.warning("No repositories found.")
            return
        
        logging.info(f"Found {len(repos)} repositories.")
        for repo in tqdm(repos, total=len(repos), desc=f"Analyzing repositories..."):
            try:
                structure = StructureFilter(repo, self.config)
                if structure.is_valid() and (self.config.popular or self.config.output_file):
                    Writer(structure.repo.full_name, self.config.output_file).write_repo()
                self.stats += structure.stats

            except Exception as e:
                logging.exception(f"[{repo}] Error analyzing: {e}")

        self.stats.write_final_log()
