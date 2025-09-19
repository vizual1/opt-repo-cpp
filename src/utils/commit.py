import os, logging, base64
import requests, zipfile, io

def get_repo_ids(path: str, url: str = "") -> list[str]:
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

def get_filtered_commits(path: str) -> list:
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


def get_repo_tree(owner: str, name: str) -> tuple[list, str]:
    commit_url = f"https://api.github.com/repos/{owner}/{name}/commits/HEAD"
    commit_resp = requests.get(commit_url)
    commit_resp.raise_for_status()
    commit_sha = commit_resp.json()["sha"]

    tree_url = f"https://api.github.com/repos/{owner}/{name}/git/trees/{commit_sha}?recursive=1"
    tree_resp = requests.get(tree_url)
    tree_resp.raise_for_status()
    tree_data = tree_resp.json()
    
    cmake_files = [item for item in tree_data.get("tree", []) if item["type"] == "blob" and item["path"].endswith("CMakeLists.txt")]
    return cmake_files, commit_sha

def has_root_cmake(cmake_files: list) -> bool:
    """
    Check whether a repo has a CMakeLists.txt at the root.
    """
    for item in cmake_files:
        if item["type"] == "blob" and item["path"] == "CMakeLists.txt":
            return True
    return False

def get_cmakelists(owner: str, name: str, commit_sha: str, cmake_files: list, dest: str):
    """
    Fetch only CMakeLists.txt files from a GitHub repo using API calls, preserving folder structure.
    """
    os.makedirs(dest, exist_ok=True)

    for file_info in cmake_files:
        path = file_info["path"]
        contents_url = f"https://api.github.com/repos/{owner}/{name}/contents/{path}?ref={commit_sha}"
        content_resp = requests.get(contents_url)
        content_resp.raise_for_status()
        content_data = content_resp.json()

        file_bytes = base64.b64decode(content_data["content"])

        target_path = os.path.join(dest, path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(file_bytes)

    return [f["path"] for f in cmake_files]