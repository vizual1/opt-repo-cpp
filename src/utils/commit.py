import os, logging, base64
import requests, zipfile, io
from github.Repository import Repository
from github.GitTreeElement import GitTreeElement

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

def get_filtered_commits(path: str) -> list[tuple[str, str]]:
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

def get_commit(repo_url: str, repo_path: str) -> None:
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

def has_root_cmake(cmake_files: list) -> bool:
    """
    Check whether a repo has a CMakeLists.txt at the root.
    """
    for item in cmake_files:
        if item.type == "blob" and item.path == "CMakeLists.txt":
            return True
    return False

def get_repo_tree(repo: Repository) -> list[GitTreeElement]:
    head = repo.get_commits()[0]
    tree = repo.get_git_tree(head.sha, recursive=True)
    cmake_files = [item for item in tree.tree if item.type == "blob" and item.path.endswith("CMakeLists.txt")]
    return cmake_files

def get_cmakelists(repo: Repository, cmake_files: list[GitTreeElement], dest: str) -> list[str]:
    """
    Fetch only CMakeLists.txt files from a GitHub repo using API calls, preserving folder structure.
    """
    os.makedirs(dest, exist_ok=True)
    head = repo.get_commits()[0]

    for cmake_file in cmake_files:
        cmake_path = cmake_file.path
        content_file = repo.get_contents(cmake_path, ref=head.sha)

        assert not isinstance(content_file, list), f"{cmake_path} should be a CMakeLists.txt"
        file_bytes = base64.b64decode(content_file.content)

        target_path = os.path.join(dest, cmake_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(file_bytes)

    return [f.path for f in cmake_files]
