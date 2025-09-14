import os, argparse, logging
from src.crawler import GithubCrawler
from src.test import Tester
from src.docker.generator import DockerBuilder

# TODO: input arguments: 
# -repo="url_link" (optional, otherwise read from data/repo_urls.txt)
# -filter="simple" ("LLM", others)
# --test with --inplace (default) or --full (installs all the filtered repo and test them one by one)
# if not --test then create filtered history of repo commits 
# else check if filtered history of repo commits already exists => no then create filtered history

def start():
    parser = argparse.ArgumentParser(description="Collect, Filter and Test C++ Github Repositories.")

    parser.add_argument("-repo", type=str, default="", help="GitHub Repo URL (optional) (default: repo_urls in config.py).")
    parser.add_argument("-sha", type=str, default="", help="Select a certain repository commit version.")
    #parser.add_argument("-filter", type=str, choices=["simple", "LLM", "custom"], default="simple", help="Filter strategy to use (default: simple).")
    
    parser.add_argument("--crawl", action="store_true", help="Collect and filter commits history.")
    parser.add_argument("--separate", action="store_true", help="Saves each filtered commit separately with commit message and diff.")

    parser.add_argument("--docker", action="store_true", help="Create Dockerfiles for testing.")
    parser.add_argument("--ignore_conflict", action="store_true", help="Ignores possible package conflicts while generating Dockerfile.")
    
    parser.add_argument("--test", action="store_true", help="Run tests on the filtered repositories.")
    
    #test_mode = parser.add_mutually_exclusive_group()
    #test_mode.add_argument("--inplace", action="store_true", help="Test repos in place (default).")
    #test_mode.add_argument("--full", action="store_true", help="Install and test all repos one by one.")

    args = parser.parse_args()

    if args.crawl:
        logging.info("Starting Github Crawler...")
        crawler = GithubCrawler(url=args.repo, sha=args.sha, separate=args.separate)
        crawler.crawl()

    if args.docker:
        logging.info("Building Dockerfile...")
        docker = DockerBuilder(url=args.repo)
        docker.create(sha=args.sha, ignore_conflict=args.ignore_conflict)

    if args.test:
        logging.info("Starting Testing...")
        tester = Tester() 
        tester.test(url=args.repo)

    return 0