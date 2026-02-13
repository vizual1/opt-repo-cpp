import argparse
from src.core.controller import Controller
from src.config.config import Config

def setup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GitHub automation tool: crawl repos, gather commits, and run tests.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # === Mode selection ===
    mode = parser.add_argument_group()
    mode.add_argument("--collect", action="store_true",
                      help="Collect C++ Repositories from GitHub. Set with --limit and --stars flags.")
    mode.add_argument("--testcollect", action="store_true",
                      help="Test and validate collected C++ Repositories from GitHub.")
    mode.add_argument("--commits", action="store_true",
                      help="Gather and filter commits from C++ Repositories.")
    mode.add_argument("--testcommits", action="store_true",
                      help="Test commits between two versions and generates a commit file.")
    mode.add_argument("--test", action="store_true",
                      help="Call --testcollect on --collect output, or --testcommits on --commits output.")
    mode.add_argument("--genimages", action="store_true",
                      help="Given a folder of json files generated via the --testcommits flag, " \
                      "generate and save docker images (no test is run here) of each json file.")
    mode.add_argument("--pushimages", action="store_true",
                      help="Given a folder of json files generated via the --testcommits flag, " \
                      "push the image to Dockerhub.")
    mode.add_argument("--testdocker", action="store_true",
                      help="Build and test docker images. " \
                      "Given a file of docker images 'owner_repo_newsha' with commits in " \
                      "'/test_workspace/workspace/new' and '/test_workspace/workspace/old' " \
                      "Docker images should be named 'owner_repo_newsha' or 'dockerhub_user/dockerhub_repo:owner_repo_newsha'")
    mode.add_argument("--patch", action="store_true",
                      help="Given owner/repo (repo_id), a commit SHA value and a prompt " \
                      "use OpenHands to generate a patch. Generates a diff file.")
    mode.add_argument("--testpatch", action="store_true",
                      help="Build and test docker images." \
                      "Given a file of docker images (or a docker image tar files) with a " \
                      "commit at '/test_workspace/workspace/old' and its patch in '/test_workspace/workspace/patch'. " \
                      "Docker images should be named 'owner_repo_newsha' or 'dockerhub_user/dockerhub_repo:owner_repo_newsha'")
    
    

    # === Input / Output ===
    io_group = parser.add_argument_group("Input / Output Options")
    io_group.add_argument("--input", type=str,
                          help="Path to input file (e.g., crawl.txt).")
    io_group.add_argument("--output", type=str, default="data/results.txt",
                          help="Output file path (default: data/results.txt).")
    io_group.add_argument("--repo", type=str,
                          help="Repository URL or repo full name (e.g., owner/repo).")
    io_group.add_argument("--prompt", type=str,
                          help="Prompt for OpenHands")

    # === Commit options ===
    commit_group = parser.add_argument_group("Commit Options")
    commit_group.add_argument("--sha", type=str,
                              help="SHA for testing.")

    # === Filtering / Analysis ===
    filter_group = parser.add_argument_group("Filtering and Analysis Options")
    filter_group.add_argument("--limit", type=int, default=10,
                              help="Limit number of repositories or commits (default: 10).")
    filter_group.add_argument("--stars", type=int, default=1000,
                              help="Minimum star count for popular repos (default: 1000).")
    filter_group.add_argument("--filter", type=str, choices=["simple", "llm", "issue"],
                              default="llm", help="Filter strategy to use (default: llm).")

    # === Docker / Testing ===
    docker_group = parser.add_argument_group("Docker and Testing Options")
    docker_group.add_argument("--tar", type=str,
                              help="Saves the docker image as a tar file.")
    docker_group.add_argument("--docker", type=str,
                              help="Docker image to create a docker container that builds and tests the commits.")
    docker_group.add_argument("--mount", type=str,
                              help="Mounts a folder to the docker container.")
    docker_group.add_argument("--diff", type=str,
                              help="Applies the diff patch to the old (original) commit in the docker container.")
    return parser


def create_config(args: argparse.Namespace) -> Config:
    """Create a Config object from argparse arguments."""
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
