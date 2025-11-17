import argparse, sys
from src.core.controller import Controller
from src.config.config import Config


def setup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GitHub automation tool: crawl repos, gather commits, and run tests.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Examples:
        python main.py --popular --stars 1000 --limit 10
        python main.py --testcrawl --input data/crawl.txt
        python main.py --commits --repo gabime/spdlog
        python main.py --testcommits --input data/test.txt
        python main.py --test --mount data/repo --docker cpp-base
        """
    )

    # === Mode selection ===
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

    # === Input / Output ===
    io_group = parser.add_argument_group("Input / Output Options")
    io_group.add_argument("--input", type=str,
                          help="Path to input file (e.g., crawl.txt).")
    io_group.add_argument("--output", type=str, default="data/results.txt",
                          help="Output file path (default: data/results.txt).")
    io_group.add_argument("--repo", type=str,
                          help="Repository URL or slug (e.g., owner/repo).")

    # === Commit options ===
    commit_group = parser.add_argument_group("Commit Options")
    commit_group.add_argument("--sha", type=str,
                              help="SHA for testing.")
    commit_group.add_argument("--newsha", type=str,
                              help="New commit SHA for comparison.")
    commit_group.add_argument("--oldsha", type=str,
                              help="Old commit SHA for comparison.")
    commit_group.add_argument("--separate", action="store_true",
                              help="Save each filtered commit separately with commit message and diff.")

    # === Filtering / Analysis ===
    filter_group = parser.add_argument_group("Filtering and Analysis Options")
    filter_group.add_argument("--limit", type=int, default=10,
                              help="Limit number of repositories or commits (default: 10).")
    filter_group.add_argument("--stars", type=int, default=1000,
                              help="Minimum star count for popular repos (default: 1000).")
    filter_group.add_argument("--filter", type=str, choices=["simple", "llm", "issue"],
                              default="simple", help="Filter strategy to use (default: simple).")
    filter_group.add_argument("--analyze", action="store_true",
                              help="Analyze the given repositories.")

    # === Docker / Testing ===
    docker_group = parser.add_argument_group("Docker and Testing Options")
    docker_group.add_argument("--docker", type=str,
                              help="Docker image to build and test repositories or commits.")
    docker_group.add_argument("--mount", type=str,
                              help="Mount directory to Docker, build, test, and evaluate against old commit.")

    return parser


def create_config(args: argparse.Namespace) -> Config:
    """Create a Config object from argparse arguments."""
    # Unpack all args directly into Config (thanks to dataclasses)
    cfg = Config(**vars(args))
    return cfg


def start() -> None:
    parser = setup_parser()
    args = parser.parse_args()

    config = create_config(args)
    pipeline = Controller(config=config)
    pipeline.run()


if __name__ == "__main__":
    start()
