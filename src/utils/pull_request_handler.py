import os
from github import Github, Auth
from github.Repository import Repository
from github.Commit import Commit
from tqdm import tqdm
from src.config.config import Config
from src.core.filter.commit_filter import CommitFilter

# Helpful script to handle pull requests for commits
# Merge commits that are linked to the same PR

TOKEN = os.getenv("GITHUB_ACCESS_TOKEN", "")
if not TOKEN:
    raise RuntimeError("GITHUB_ACCESS_TOKEN not set")

auth = Auth.Token(TOKEN)
g = Github(auth=auth)

# Caches
commit_to_pr_cache = {} # (repo_full, sha) -> pr_number or None
pr_info_cache = {}      # (repo_full, pr_number) -> (head_sha, merge_base_sha)
emitted_prs = set()     # (repo_full, pr_number)

# Helpers
def parse_line(line):
    parts = [p.strip() for p in line.split("|")]
    if len(parts) != 3:
        raise ValueError(f"Invalid line: {line}")
    return parts[0], parts[1], parts[2]

repo_cache = {}

def get_repo(repo_full):
    if repo_full not in repo_cache:
        repo_cache[repo_full] = g.get_repo(repo_full)
    return repo_cache[repo_full]

def get_pr_for_commit(repo, repo_full, sha):
    """Return PR number or None"""
    key = (repo_full, sha)
    if key in commit_to_pr_cache:
        return commit_to_pr_cache[key]

    headers = {"Accept": "application/vnd.github.groot-preview+json"}
    url = f"{repo.url}/commits/{sha}/pulls"
    try:
        _, prs = repo._requester.requestJsonAndCheck(
            "GET", url, headers=headers
        )
    except Exception as e:
        print(f"Exception: {e}")
        return None

    if not prs:
        commit_to_pr_cache[key] = None
        return None

    # Prefer merged PRs targeting default branch
    merged = [pr for pr in prs if pr.get("merged_at")]
    pr = merged[0] if merged else prs[0]

    pr_number = pr["number"]
    commit_to_pr_cache[key] = pr_number
    return pr_number

def get_pr_chain_msg(repo: Repository, commit: Commit, is_issue: bool):
    new_sha = commit.sha
    old_sha = commit.parents[0].sha if commit.parents else "None"
    if not is_issue:
        return f"{repo.full_name} | {new_sha} | {old_sha}\n"
    pr_number = get_pr_for_commit(repo, repo.full_name, new_sha)
    if pr_number is None:
        # Not a PR commit, emit as usual
        return f"{repo.full_name} | {new_sha} | {old_sha}\n"
    
    pr = repo.get_pull(pr_number)
    comparison = repo.compare(pr.base.sha, pr.head.sha)
    original_commit = comparison.merge_base_commit.sha
    patched_commit = pr.head.sha

    return f"{repo.full_name} | {patched_commit} | {original_commit}\n"
