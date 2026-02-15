import os

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