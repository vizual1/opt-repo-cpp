import os, requests, docker, logging
from src.config.config import Config

def image(repo_id: str, sha: str) -> str:
    return ("_".join(repo_id.split("/")) + f"_{sha}").lower()

def image_exists(repo_id: str = "", sha: str = "", other: str = "") -> bool:
    image_name = other if other else image(repo_id, sha)
    client = docker.from_env()
    try:
        client.images.get(image_name)
        return True
    except docker.errors.ImageNotFound: #type:ignore
        return False
    except docker.errors.APIError: #type:ignore
        return False
    
def delete_image(repo_id: str = "", sha: str = "", other: str = "") -> None:
    image_name = other if other else image(repo_id, sha)
    client = docker.from_env()
    try:
        client.images.remove(image=image_name, force=True)
        logging.info(f"Image '{image_name}' has been deleted.")
    except docker.errors.ImageNotFound: #type:ignore
        logging.info(f"Image '{image_name}' not found.")
    except docker.errors.APIError as e: #type:ignore
        logging.info(f"Failed to delete image: {e}")

def check_dockerhub() -> tuple[str, str]:
    dockerhub_user = os.environ.get("DOCKERHUB_USER")
    dockerhub_repo = os.environ.get("DOCKERHUB_REPO")
    if not dockerhub_user:
        raise RuntimeError("DOCKERHUB_USER environment variable is not set")
    if not dockerhub_repo:
        raise RuntimeError("DOCKERHUB_REPO environment variable is not set")
    return dockerhub_user, dockerhub_repo

"""
def dockerhub_containers() -> list[str]:
    # url="https://hub.docker.com/v2/repositories/tommyho1999/opt-repo-cpp/tags?page_size=100"; while [ "$url" != "null" ]; do resp=$(curl -s "$url"); echo "$resp" | jq -r '.results[].name'; url=$(echo "$resp" | jq -r '.next'); done | wc -l
    all_images = subprocess.run()
    # extract all_images to list[str]
    return all_images
"""

def dockerhub_containers(dockerhub_user: str, dockerhub_repo: str) -> list[str]:
    tags = []
    url = f"https://hub.docker.com/v2/repositories/{dockerhub_user}/{dockerhub_repo}/tags?page_size=100"

    while url:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()

        for r in data["results"]:
            tags.append(r["name"])

        url = data["next"]  # None when no more pages

    return tags

def config_image(config: Config, repo_id: str, new_sha: str) -> bool:
    """Configure the docker image depending on flags (check, delete)."""
    local_image = image(repo_id, new_sha)

    # checks if the image is already uploaded to dockerhub given a DOCKERHUB_USER and DOCKERHUB_REPO
    if not config.genforce and config.genimages and config.check_dockerhub and local_image in config.dockerhub_containers:
        return False
    
    # deletes the docker image if it exists (because of genforce)
    if config.genforce and image_exists(repo_id, new_sha):
        logging.info("Image already exists, delete image to overwrite")
        delete_image(repo_id, new_sha)
        if config.check_dockerhub:
            remote_image = f"{config.dockerhub_user}/{config.dockerhub_repo}:{local_image}"
            delete_image(other=remote_image)
        return False

    # the docker image is already generated for repo_id and new_sha
    if config.genimages and image_exists(repo_id, new_sha):
        logging.info("Image already exists, no need to generate the docker image")
        return False
    
    return True