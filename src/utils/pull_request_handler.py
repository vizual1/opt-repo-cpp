import os
from github import Github, Auth
from tqdm import tqdm
from src.config.config import Config
from src.core.filter.commit_filter import CommitFilter

# Helpful script to handle pull requests for commits
# Merge commits that are linked to the same PR

INPUT_FILE = "data/collect/final.txt"
ALREADY_DONE = "data/collect/pr_filtered.txt"
OUTPUT_FILE = "data/collect/pr.txt"

TOKEN = os.getenv("access_token")
if not TOKEN:
    raise RuntimeError("access_token not set")

auth = Auth.Token(TOKEN)
g = Github(auth=auth)

# Caches
commit_to_pr_cache = {}       # (repo_full, sha) -> pr_number or None
pr_info_cache = {}            # (repo_full, pr_number) -> (head_sha, merge_base_sha)
emitted_prs = set()           # (repo_full, pr_number)

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

    headers = {
        "Accept": "application/vnd.github.groot-preview+json"
    }
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


def get_pr_info(repo, repo_full, pr_number):
    key = (repo_full, pr_number)
    if key in pr_info_cache:
        return pr_info_cache[key]

    pr = repo.get_pull(pr_number)

    if pr.merged:
        head_sha = pr.merge_commit_sha
        base_sha = pr.base.sha
    else:
        head_sha = pr.head.sha
        comparison = repo.compare(pr.base.sha, pr.head.sha)
        base_sha = comparison.merge_base_commit.sha

    pr_info_cache[key] = (head_sha, base_sha)
    return head_sha, base_sha

already_done = [] # already checked the pull requests for these commits
with open(ALREADY_DONE, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        already_done.append(line)

output_lines = [] # already filtered pull requests
with open(OUTPUT_FILE, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        output_lines.append(line)


# Main processing
config = Config()
with open(INPUT_FILE, "r") as f:
    for line in tqdm(f, desc="Handle Pull Requests"):
        line = line.strip()
        if not line or line in already_done:
            continue

        repo_full, new_sha, old_sha = parse_line(line)
        repo = get_repo(repo_full)

        pr_number = get_pr_for_commit(repo, repo_full, new_sha)
        if pr_number is None:
            # Not a PR commit, emit as usual
            output_lines.append(f"{repo_full} | {new_sha} | {old_sha}")
            continue

        pr = repo.get_pull(pr_number)

        comparison = repo.compare(pr.base.sha, pr.head.sha)
        original_commit = comparison.merge_base_commit.sha
        patched_commit = pr.head.sha

        if f"{repo_full} | {patched_commit} | {original_commit}" in output_lines:
            continue

        commits_in_pr = comparison.commits

        skip_pr = False
        for commit in commits_in_pr:
            if not CommitFilter(commit, config, repo).only_cpp_source_modified:
                skip_pr = True
                break

        if skip_pr:
            # Skip PR with non-C++ file modifications
            continue

        # Emit one line per PR (base and head)
        output_lines.append(f"{repo_full} | {patched_commit} | {original_commit}")


# Write output
messages = list(set(output_lines))
messages.sort(key=str.casefold)

with open(OUTPUT_FILE, "w") as f:
    for line in messages:
        f.write(line + "\n")

print(f"Wrote {len(messages)} lines to {OUTPUT_FILE}")
