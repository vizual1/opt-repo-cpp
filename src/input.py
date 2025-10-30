import argparse, sys, logging
from src.controller import Controller
from src.utils.dataclasses import Config

def start() -> None:
    parser = argparse.ArgumentParser(description="GitHub automation tool: crawl repos, gather commits, and run tests.")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--popular", action="store_true", help="Crawl GitHub for popular repositories.")
    mode.add_argument("--testcrawl", action="store_true", help="Test and validates crawled github repositories.")
    mode.add_argument("--commits", action="store_true", help="Gather and filter commits from a repo.")
    mode.add_argument("--testcommits", action="store_true", help="Test commits between two versions or commit file.")

    parser.add_argument("-limit", type=int, default=10, help="Limit crawled number of popular repositories or commits.")
    parser.add_argument("-input", type=str, help="Path to input file (e.g., crawl.txt).")
    parser.add_argument("-repo", type=str, help="Repository URL (e.g., https://github.com/owner/repo).")
    parser.add_argument("-sha", type=str, help="SHA for testing.")
    parser.add_argument("-newsha", type=str, help="New commit SHA for comparison.")
    parser.add_argument("-oldsha", type=str, help="Old commit SHA for comparison.")
    parser.add_argument("-stars", type=int, default=1000, help="Minimum star count filter for popular repos.")
    parser.add_argument("-output", type=str, help="Output file path.")
    parser.add_argument("-filter", type=str, choices=["simple", "llm", "custom"], default="simple", help="Filter strategy to use (default: simple).")
    parser.add_argument("-docker", type=str, help="Docker image to build and test the repositories or commits (default: uses cmake_minimum_required mapping to docker image defined in config.py).")
    parser.add_argument("--separate", action="store_true", help="Saves each filtered commit separately with commit message and diff.")
    parser.add_argument("--analyze", action="store_true", help="Analyze the given repos.")

    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)


    config = Config(
        popular=args.popular, 
        testcrawl=args.testcrawl, 
        commits=args.commits,
        testcommits=args.testcommits,

        limit=args.limit,
        stars=args.stars,
        repo_url=args.repo,

        input=args.input, 
        output=args.output,
        sha=args.sha,
        newsha=args.newsha,
        oldsha=args.oldsha,

        filter=args.filter, 
        docker=args.docker,
        separate=args.separate, 
        analyze=args.analyze
    )
    
    pipeline = Controller(config=config)
    pipeline.run()