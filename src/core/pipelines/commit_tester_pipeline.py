import logging, os
from tqdm import tqdm
from src.config.config import Config
from src.utils.commit import CommitHandler
from src.core.docker.tester import DockerTester
from concurrent.futures import ProcessPoolExecutor, as_completed
from src.utils.image_handling import image_exists, image, delete_image
from github.Commit import Commit

def get_available_cpus() -> list[int]:
    """Returns the list of CPUs the current process is allowed to run on."""
    try:
        cpus = sorted(os.sched_getaffinity(0))
        if cpus:
            return cpus
    except Exception:
        pass

    count = os.cpu_count() or 1
    return list(range(count))


def generate_cpu_sets(cpus: list[int], cpus_per_job: int, max_jobs: int) -> list[str]:
    cpu_sets = []
    idx = 0

    for _ in range(max_jobs):
        chunk = cpus[idx : idx + cpus_per_job]
        if len(chunk) < cpus_per_job:
            break
        cpu_sets.append(",".join(map(str, chunk)))
        idx += cpus_per_job

    if not cpu_sets:
        raise RuntimeError("Not enough CPUs for requested parallel jobs")
    return cpu_sets


def run_one_commit(repo_id: str, new_sha: str, old_sha: str, pr_shas: list[str], config: Config, cpuset_cpus: str = ""):
    try:
        # checks if the image is already uploaded to dockerhub given a DOCKERHUB_USER and DOCKERHUB_REPO
        if config.genimages and config.check_dockerhub and not config.genforce:
            local_image = image(repo_id, new_sha)
            if local_image in config.dockerhub_containers:
                return
        
        # deletes the old docker image
        if config.genforce and image_exists(repo_id, new_sha):
            delete_image(repo_id, new_sha)
            if config.check_dockerhub:
                local_image = image(repo_id, new_sha)
                remote_image = f"{config.dockerhub_user}/{config.dockerhub_repo}:{local_image}"
                delete_image(other=remote_image)

        # the docker image is already generated for repo_id and new_sha
        if config.genimages and image_exists(repo_id, new_sha):
            logging.info("Image already exists, no need to generate the docker image")
            return

        commit = CommitHandler(
            config.input_file or config.storage_paths["commits"],
            config.storage_paths["clones"],
        )

        file = commit.get_file_prefix(repo_id)

        # commits are clones into these paths
        new_path, old_path = commit.get_paths(file, new_sha, config.testdockerpatch)

        repo = config.git_client.get_repo(repo_id)
        docker = DockerTester(repo, config)
        docker.run_commit_pair(new_sha, old_sha, pr_shas, new_path, old_path, cpuset_cpus)

    except Exception:
        logging.exception(f"[{repo_id}] Error testing commits")

class CommitTesterPipeline:
    """
    This class runs the commits and evaluates its performance.
    """
    def __init__(self, config: Config):
        self.config = config
        self.commit = CommitHandler(self.config.input_file or self.config.storage_paths['commits'], self.config.storage_paths['clones'])

    def test_commit(self, commits: list[Commit] = []) -> None:
        self._input_tester(commits)

    def _input_tester(self, commits_list: list[Commit] = []) -> None:
        if self.config.genimages or self.config.testdocker or self.config.testdockerpatch:
            commits = self.commit.get_commit_from_input(self.config)
        else:
            commits = self.commit.get_commits(commits_list)
        tasks: list[tuple[str, str, str, list[str], str]] = []
        available_cpus = get_available_cpus()

        cpu_sets = generate_cpu_sets(
            cpus=available_cpus,
            cpus_per_job=2,
            max_jobs=self.config.resources.max_parallel_jobs,
        )

        logging.info(f"Available CPUs: {available_cpus}")
        logging.info(f"CPU pinning sets: {cpu_sets}")

        for i, (repo_id, new_sha, old_sha, pr_shas) in enumerate(commits):
            cpu_set = cpu_sets[i % len(cpu_sets)]
            tasks.append((repo_id, new_sha, old_sha, pr_shas, cpu_set))

        with ProcessPoolExecutor(max_workers=len(cpu_sets)) as executor:
            futures = [
                executor.submit(run_one_commit, repo_id, new_sha, old_sha, pr_shas, self.config, cpu_set)
                for repo_id, new_sha, old_sha, pr_shas, cpu_set in tasks
            ]

            for future in tqdm(as_completed(futures), total=len(futures)):
                future.result()
