import logging, os
from tqdm import tqdm
from src.config.config import Config
from src.utils.commit import CommitHandler
from src.core.docker.tester import DockerTester
from concurrent.futures import ProcessPoolExecutor, as_completed
from src.utils.image_handling import config_image
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


def run_one_commit(repo_id: str, new_sha: str, old_sha: str, config: Config, cpuset_cpus: str = ""):
    try:
        if not config_image(config, repo_id, new_sha):
            return

        commit = CommitHandler("", config.storage_paths["clones"])
        file = commit.get_file_prefix(repo_id)

        # commits are cloned into these paths
        new_path, old_path = commit.get_paths(file, new_sha)

        repo = config.git_client.get_repo(repo_id)
        docker = DockerTester(repo, config)
        docker.run_commit_pair(new_sha, old_sha, new_path, old_path, cpuset_cpus)

    except Exception as e:
        logging.exception(f"[{repo_id}] Error testing commits: {e}")

class CommitTesterPipeline:
    """
    This class runs the commits and evaluates its performance.
    """
    def __init__(self, config: Config):
        self.config = config
        self.commit = CommitHandler(self.config.input_file or self.config.storage_paths['commits'], self.config.storage_paths['clones'])

    def test_commit(self, commits_list: list[Commit] = []) -> None:
        if self.config.docker_image:
            owner, name, new_sha = tuple(self.config.docker_image.split("_"))
            repo_id = f"{owner}/{name}"
            old_sha = self.config.git_client.get_repo(repo_id).get_commit(new_sha).parents[0].sha
            commits = [(repo_id, new_sha, old_sha)]
        else:
            commits = self.commit.get_commits(commits_list)
        if len(commits) > 0:
            logging.info(f"Commits found {len(commits)}")
        tasks: list[tuple[str, str, str, str]] = []
        available_cpus = get_available_cpus()

        cpu_sets = generate_cpu_sets(
            cpus=available_cpus,
            cpus_per_job=2,
            max_jobs=self.config.resources.max_parallel_jobs,
        )

        logging.info(f"Available CPUs: {available_cpus}")
        logging.info(f"CPU pinning sets: {cpu_sets}")

        for i, (repo_id, new_sha, old_sha) in enumerate(commits):
            cpu_set = cpu_sets[i % len(cpu_sets)]
            tasks.append((repo_id, new_sha, old_sha, cpu_set))

        with ProcessPoolExecutor(max_workers=len(cpu_sets)) as executor:
            futures = [
                executor.submit(run_one_commit, repo_id, new_sha, old_sha, self.config, cpu_set)
                for repo_id, new_sha, old_sha, cpu_set in tasks
            ]

            for future in tqdm(as_completed(futures), total=len(futures)):
                future.result()

        