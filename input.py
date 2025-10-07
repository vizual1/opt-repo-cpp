import argparse
from src.controller import Controller
from src.utils.dataclasses import Config

def start() -> None:
    parser = argparse.ArgumentParser(description="Collect, Filter and Test C++ Github Repositories.")

    parser.add_argument("--crawl", action="store_true", help="Collect and filter commits history.")
    parser.add_argument("--docker", action="store_true", help="Create Dockerfiles for testing.")
    parser.add_argument("--test", action="store_true", help="Run tests on the filtered repositories.")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-url", type=str, default="", help="GitHub Repo URL (optional).")
    group.add_argument("--popular", action="store_true", help="Collect and filter popular repositories from Github. If set then it will skip the set '-url'.")
    parser.add_argument("-stars", type=int, default=1000, help="Selects only repositories with more than x stars.")
    parser.add_argument("-limit", type=int, default=10, help="Selects x amount of repositories.")
    
    group.add_argument("-read", type=str, default="", help="Filepath to read in GitHub URLs.")
    parser.add_argument("-write", type=str, default="", help="Filepath to write GitHub URLs.")

    parser.add_argument("-sha", type=str, default="", help="Select a certain commit version of some Github repository.")
    parser.add_argument("-filter", type=str, choices=["simple", "LLM", "custom"], default="simple", help="Filter strategy to use (default: simple).")
    parser.add_argument("--separate", action="store_true", help="Saves each filtered commit separately with commit message and diff.")
    parser.add_argument("--analyze", action="store_true", help="Analyze the given repos")

    parser.add_argument("--ignore_conflict", action="store_true", help="Ignores possible package conflicts while generating Dockerfile.")
    
    args = parser.parse_args()
    
    config = Config(
        read=args.read, write=args.write,
        popular=args.popular, stars=args.stars, limit=args.limit,
        filter=args.filter, separate=args.separate, analyze=args.analyze,
        ignore_conflict=args.ignore_conflict
    )

    pipeline = Controller(
        crawl=args.crawl, docker=args.docker, test=args.test,
        url=args.url, sha=args.sha, config=config
    )
    pipeline.run()