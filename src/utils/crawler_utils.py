import os
import requests, zipfile, io, shutil
import subprocess

def extract_repo_ids(path: str, url: str = "") -> list[str]:
    """Extract repository IDs (owner/repo) from GitHub URLs."""
    repo_ids: list[str] = []

    if not url:
        with open(path, 'r') as f:
            urls = f.readlines()
        for url in urls:
            repo_ids.append(url[len("https://github.com/"):].strip())
    else:
        repo_ids.append(url[len("https://github.com/"):].strip())

    return repo_ids

def extract_filtered_commits(path: str) -> list:
    """Extract commit information from a file."""
    with open(path, 'r') as f:
        filtered_commits = f.readlines()

    commits_info: list = []
    for commit in filtered_commits:
        commit_info = commit.split("|")
        commits_info.append((commit_info[1].strip(), commit_info[2].strip()))

    return commits_info
    
def write_commits(path: str, msg: str) -> None:
    """Append a commit message and related infos to a file."""
    with open(path, 'a', errors='ignore') as f:
        f.write(msg + "\n")

def ensure_repo(repo_url: str, repo_path: str):
    """Ensure repo_path is a valid git repo, otherwise clone it fresh."""
    if not os.path.exists(repo_path):
        subprocess.run(["git", "clone", "--no-checkout", repo_url, repo_path], check=True)
    elif not os.path.exists(os.path.join(repo_path, ".git")):
        shutil.rmtree(repo_path)
        subprocess.run(["git", "clone", "--no-checkout", repo_url, repo_path], check=True)

def checkout_commit(repo_path: str, sha: str):
    """Fetch and checkout a specific commit."""
    # TODO: somehow get the diff from here?
    subprocess.run(["git", "-C", repo_path, "fetch", "--depth", "1", "origin", sha], check=True)
    subprocess.run(["git", "-C", repo_path, "checkout", sha], check=True)

def get_commit(repo_url: str, repo_path: str):
    """Fetch and extract a commit with zipball.""" 
    os.makedirs(repo_path, exist_ok=True)
    response = requests.get(repo_url, stream=True)
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        zip_ref.extractall(repo_path)
