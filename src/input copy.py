import argparse, sys
from src.controller import Controller
from src.utils.config import Config

import argparse
import sys
from typing import Optional
from src.controller import Controller
from src.utils.config import Config


def setup_parser() -> argparse.ArgumentParser:
    """Set up and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="GitHub automation tool: crawl repos, gather commits, and run tests.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=
        """
        Examples:
            python main.py --popular -stars=1000 -limit=10
            python main.py --testcrawl -input="data/crawl.txt
            python main.py --commits -repo="gabime/spdlog"
            python main.py --testcommits -input="data/test.txt"
            python main.py --test -mount="data/repo" -docker="cpp-base"
        """
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--popular", action="store_true", 
                     help="Crawl GitHub for popular repositories.")
    mode.add_argument("--testcrawl", action="store_true", 
                     help="Test and validate crawled GitHub repositories.")
    mode.add_argument("--commits", action="store_true", 
                     help="Gather and filter commits from a repository.")
    mode.add_argument("--testcommits", action="store_true", 
                     help="Test commits between two versions or commit file.")
    mode.add_argument("--test", action="store_true", 
                     help="Test Docker images or compare mounted and old commit.")

    io_group = parser.add_argument_group("Input/Output Options")
    io_group.add_argument("-input", type=str, 
                         help="Path to input file (e.g., crawl.txt).")
    io_group.add_argument("-output", type=str, 
                         help="Output file path.")
    io_group.add_argument("-repo", type=str, 
                         help="Repository URL (e.g., https://github.com/owner/repo).")

    commit_group = parser.add_argument_group("Commit Options")
    commit_group.add_argument("-sha", type=str, 
                            help="SHA for testing.")
    commit_group.add_argument("-newsha", type=str, 
                            help="New commit SHA for comparison.")
    commit_group.add_argument("-oldsha", type=str, 
                            help="Old commit SHA for comparison.")
    commit_group.add_argument("--separate", action="store_true", 
                            help="Save each filtered commit separately with commit message and diff.")
    
    filter_group = parser.add_argument_group("Filtering and Analysis Options")
    filter_group.add_argument("-limit", type=int, default=10, 
                            help="Limit crawled number of popular repositories or commits.")
    filter_group.add_argument("-stars", type=int, default=1000, 
                            help="Minimum star count filter for popular repos.")
    filter_group.add_argument("-filter", type=str, 
                            choices=["simple", "llm", "custom"], default="simple", 
                            help="Filter strategy to use (default: simple).")
    filter_group.add_argument("--analyze", action="store_true", 
                            help="Analyze the given repositories.")

    docker_group = parser.add_argument_group("Docker and Testing Options")
    docker_group.add_argument("-docker", type=str, 
                            help="Docker image to build and test repositories or commits.")
    docker_group.add_argument("-mount", type=str, 
                            help="Mount directory to Docker, build, test and evaluate against old commit.")

    return parser

def start() -> None:
    parser = argparse.ArgumentParser(description="GitHub automation tool: crawl repos, gather commits, and run tests.")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--popular", action="store_true", help="Crawl GitHub for popular repositories.")
    mode.add_argument("--testcrawl", action="store_true", help="Test and validates crawled github repositories.")
    mode.add_argument("--commits", action="store_true", help="Gather and filter commits from a repo.")
    mode.add_argument("--testcommits", action="store_true", help="Test commits between two versions or commit file.")
    mode.add_argument("--test", action="store_true", help="Testing docker images or testing between mounted and old commit.")

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
    parser.add_argument("-mount", type=str, help="Mounts the directory to the set docker. Builds, tests and evalutes it against the old commit.")
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
        test=args.test,

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
        mount=args.mount,
        separate=args.separate, 
        analyze=args.analyze
    )
    
    pipeline = Controller(config=config)
    pipeline.run()