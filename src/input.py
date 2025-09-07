import os, argparse, logging
from src.crawler import GithubCrawler
from src.test import Tester

# TODO: input arguments: 
# -repo="url_link" (optional, otherwise read from data/repo_urls.txt)
# -filter="simple" ("LLM", others)
# --test with --inplace (default) or --full (installs all the filtered repo and test them one by one)
# if not --test then create filtered history of repo commits 
# else check if filtered history of repo commits already exists => no then create filtered history

def start():
    parser = argparse.ArgumentParser(description="Collect, Filter and Test C++ Github Repositories.")

    parser.add_argument("-repo", type=str, default="", help="GitHub Repo URL (optional) (default: repo_urls in config.py).")
    parser.add_argument("-filter", type=str, choices=["simple", "LLM", "custom"], default="simple", help="Filter strategy to use (default: simple).")
    parser.add_argument("--test", action="store_true", help="Additionally run tests on the repositories.")

    #test_mode = parser.add_mutually_exclusive_group()
    #test_mode.add_argument("--inplace", action="store_true", help="Test repos in place (default).")
    #test_mode.add_argument("--full", action="store_true", help="Install and test all repos one by one.")

    args = parser.parse_args()

    logging.info("Starting Github Crawler")

    crawler = GithubCrawler()
    crawler.crawl_repos(args.repo)

    logging.info("Starting Testing")

    if args.test:
        tester = Tester() 
        tester.test(url=args.repo)

    return 0