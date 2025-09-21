import argparse, logging
from src.crawler import GithubCrawler
from src.test import Tester
from src.docker.generator import DockerBuilder

def start():
    parser = argparse.ArgumentParser(description="Collect, Filter and Test C++ Github Repositories.")

    parser.add_argument("--crawl", action="store_true", help="Collect and filter commits history.")
    parser.add_argument("-url", type=str, default="", help="GitHub Repo URL (optional) (default: repo_urls in config.py).")
    parser.add_argument("-filter", type=str, choices=["simple", "LLM", "custom"], default="simple", help="Filter strategy to use (default: simple).")
    parser.add_argument("-sha", type=str, default="", help="Select a certain repository commit version.")
    parser.add_argument("--separate", action="store_true", help="Saves each filtered commit separately with commit message and diff.")

    parser.add_argument("--popular", action="store_true", help="Collect and filter popular repos from github.")
    parser.add_argument("-stars", type=int, default=1000, help="Selects only repos with more than x number of stars.")
    parser.add_argument("-limit", type=int, default=5, help="Selects x amount of repos.")

    parser.add_argument("--docker", action="store_true", help="Create Dockerfiles for testing.")
    parser.add_argument("--ignore_conflict", action="store_true", help="Ignores possible package conflicts while generating Dockerfile.")
    
    parser.add_argument("--test", action="store_true", help="Run tests on the filtered repositories.")

    args = parser.parse_args()

    if args.crawl:
        logging.info("Starting Github Crawler...")
        crawler = GithubCrawler(url=args.url, filter=args.filter, sha=args.sha, separate=args.separate,
                                popular=args.popular, stars=args.stars, limit=args.limit)
        crawler.crawl()

    if args.docker:
        logging.info("Building Dockerfile...")
        docker = DockerBuilder(url=args.url)
        docker.create(sha=args.sha, ignore_conflict=args.ignore_conflict)

    if args.test:
        logging.info("Starting Testing...")
        tester = Tester() 
        tester.test(url=args.url)

    return 0