import os, logging
import requests, zipfile, io
from src.utils.cmake_adapter import CMakeAdapter

def extract_repo_ids(path: str, url: str = "") -> list[str]:
    """Extract repository IDs (owner/repo) from GitHub URLs."""
    repo_ids: list[str] = []

    if not url:
        with open(path, 'r', errors='ignore') as f:
            urls = f.readlines()
        for url in urls:
            repo_ids.append(url.removeprefix("https://github.com/").strip())
    else:
        repo_ids.append(url.removeprefix("https://github.com/").strip())

    return repo_ids

def extract_filtered_commits(path: str) -> list:
    """Extract commit information from a file."""
    commits_info: list = []
    with open(path, 'r', errors='ignore') as f:
        for line in f:
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                commits_info.append((parts[0].strip(), parts[1].strip()))
            else:
                logging.warning(f"Malformed commit line: {line.strip()}")

    return commits_info
    
def write_commits(path: str, msg: str) -> None:
    """Append a commit message and related infos to a file."""
    with open(path, 'a', encoding="utf-8", errors='ignore') as f:
        f.write(msg + "\n")

def get_commit(repo_url: str, repo_path: str):
    """Fetch and extract a commit with zipball.""" 
    os.makedirs(repo_path, exist_ok=True)
    response = requests.get(repo_url)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        top_level = zip_ref.namelist()[0].split("/")[0]
        for member in zip_ref.namelist():
            rel_path = os.path.relpath(member, top_level)
            if rel_path == ".":
                continue
            target_path = os.path.join(repo_path, rel_path)
            if member.endswith("/"):
                os.makedirs(target_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with zip_ref.open(member) as source, open(target_path, "wb") as target:
                    target.write(source.read())
