import os, logging, base64
import requests, zipfile, io
from github.Repository import Repository
from github.GitTreeElement import GitTreeElement
from github.GitTree import GitTree
import src.config as conf

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
    
def write(path: str, msg: str) -> None:
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

def has_root_cmake(cmake_files: list[GitTreeElement]) -> bool:
    """
    Check whether a repo has a CMakeLists.txt at the root.
    """
    for item in cmake_files:
        if item.type == "blob" and item.path == "CMakeLists.txt":
            return True
    return False

def has_test_dir(tree_paths: list[str]) -> bool:
    """
    Check whether a repo has valid test directories.
    """
    for item in tree_paths:
        for tdir in conf.TEST_DIR:
            if item.startswith(tdir):
                return True
    return False

def get_repo_tree(repo: Repository, sha: str) -> tuple[list[GitTreeElement], list[str], list[GitTreeElement]]:
    head = repo.get_commits()[0]
    tree = repo.get_git_tree(head.sha, recursive=True).tree
    tree_paths = [item.path for item in tree]
    cmake_files = [item for item in tree if item.type == "blob" and item.path.endswith("CMakeLists.txt")]
    return cmake_files, tree_paths, tree

def get_cmakelists(repo: Repository, cmake_files: list[GitTreeElement], dest: str) -> list[str]:
    """
    Fetch only CMakeLists.txt files from a GitHub repo using API calls, preserving folder structure.
    """
    os.makedirs(dest, exist_ok=True)

    head = repo.get_commits()[0]
    sha = head.sha
    owner, name = repo.full_name.split("/")
    base_url = f"https://raw.githubusercontent.com/{owner}/{name}/{sha}"

    result_paths = []
    for item in cmake_files:
        url = f"{base_url}/{item.path}"
        try:
            r = requests.get(url)
            r.raise_for_status()

            target_path = os.path.join(dest, item.path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "wb") as f:
                f.write(r.content)

            result_paths.append(target_path)
        except Exception:
            logging.info(f"Failed to get {url}")
            continue

    return result_paths

def extract_test_dirs(tree: list[GitTreeElement]) -> set[str]:
    """
    Extracts all directories that look like test-related dirs from a PyGithub GitTree.
    """
    test_dirs = set()

    for element in tree: 
        path = element.path.lower()
        parts = path.split("/")

        for i, part in enumerate(parts[:-1]):
            if any(keyword in part for keyword in conf.TEST_KEYWORDS):
                test_dir = "/".join(parts[:i+1])
                test_dirs.add(test_dir)

    top_level_dirs = set()
    for dir_path in test_dirs:
        if not any(dir_path != other and dir_path.startswith(other + "/")
                   for other in test_dirs):
            top_level_dirs.add(dir_path)

    return top_level_dirs
