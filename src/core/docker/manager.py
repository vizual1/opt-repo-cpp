import logging, posixpath, docker, os, time, shlex
from pathlib import Path
from docker.types import Mount
from typing import Optional
from src.config.config import Config
from src.utils.permission import check_and_fix_path_permissions

class DockerManager:
    def __init__(self, config: Config, mount: Path, docker_image: str, docker_test_dir: str, new: bool = False):
        self.config = config
        self.mount = mount
        self.docker_image = docker_image
        self.new = new
        self.docker_test_dir = docker_test_dir

    def stop_container(self, repo_id: str) -> None:
        if self.container:
            try:
                self.container.stop()
                self.container.remove()
                self.container = None
                logging.info(f"[{repo_id}] Stopped the container")
            except Exception as e:
                logging.warning(f"[{repo_id}] Failed to stop container: {e}")

    def start_docker_container(self, container_name: str, cpuset_cpus: str = "") -> None:
        self.client = docker.from_env()
        try:
            try:
                c = self.client.containers.get(container_name)
                c.reload()

                if c.status != "running":
                    logging.info(
                        f"Container {container_name} exists but is {c.status}, recreating"
                    )
                    c.remove(force=True)
                    raise docker.errors.NotFound(container_name) # type: ignore

                logging.info(f"Reusing running container {container_name}")
                self.container = c
                return

            except docker.errors.NotFound: # type: ignore
                pass
            
            if not check_and_fix_path_permissions(self.mount):
                return

            logging.info(f"Run docker image ({self.docker_image}) mounted on {str(self.mount)}.")
            mount = Mount(
                target="/workspace", source=str(self.mount), type="bind", read_only=False
            )
            self.container = self.client.containers.run(
                self.docker_image,
                command=["/bin/bash"],
                name=container_name,
                mounts=[mount],
                working_dir="/workspace",
                detach=True,
                tty=True,
                remove=False,

                cpuset_cpus=cpuset_cpus or self.config.resources.cpuset_cpus,
                mem_limit=self.config.resources.mem_limit,
                memswap_limit=self.config.resources.memswap_limit,
                cpu_quota=self.config.resources.cpu_quota,
                cpu_period=self.config.resources.cpu_period
            )
            mkdir_cmd = ["mkdir", "-p", f"{self.docker_test_dir}"]
            self.container.exec_run(mkdir_cmd)
            mkdir_cmd = ["mkdir", "-p", f"{self.docker_test_dir}/logs"]
            self.container.exec_run(mkdir_cmd)
        except Exception as e:
            logging.error(f"Docker execution failed: {e}")

    def clone_in_docker(self, cmd: list[str], workdir: Optional[Path] = None, check: bool = True):
        if not self.container:
            logging.error(f"No docker container started")
            return 1, "", "", -1.0
        
        if workdir:
            container_workdir = posixpath.abspath(workdir)
            exit_code, output = self.container.exec_run(cmd, workdir=str(container_workdir))
        else:
            exit_code, output = self.container.exec_run(cmd)

        if exit_code == 0:
            logging.info(f"Command run in docker: {cmd}")
        else:
            logging.warning(f"Command failed in docker: {cmd}")
        output = output.decode(errors="ignore") if output else ""
        logs = self.container.logs().decode()
        if output: logging.info(f"Output: {output}")
        if logs: logging.info(f"Logs: {logs}")


    def run_command_in_docker(self, cmd: list[str], root: Path, workdir: Optional[Path] = None, check: bool = True, timeout: int = -1, log: bool = True) -> tuple[int, str, str, float]:
        rel_root = os.path.relpath(root, self.mount)
        container_root = posixpath.join(f"/workspace", rel_root.replace("\\", "/"))

        if workdir:
            rel_workdir = os.path.relpath(workdir, self.mount).replace("\\", "/")
            container_workdir = posixpath.join(f"/workspace", rel_workdir)
        else:
            container_workdir = container_root
        
        if not self.container:
            logging.error(f"No docker container started")
            return 1, "", "", -1.0

        cmd = [str(x) for x in cmd]
        if timeout > 0:
            cmd = ["timeout", f"{timeout}s"] + cmd
        shell_cmd = shlex.join(cmd)
        timed_cmd = [
            "sh", "-c",
            f'start=$(date +%s%N); {shell_cmd}; status=$?; end=$(date +%s%N); '
            f'echo $(( (end - start)/1000000 ))" ms"; exit $status'
        ]
        start = time.perf_counter()
        exit_code, output = self.container.exec_run(timed_cmd, workdir=str(container_workdir))
        if exit_code == 0 and log:
            logging.info(f"Command run in docker: {cmd}")
        elif log:
            logging.warning(f"Command failed in docker: {cmd}")
        end = time.perf_counter()
        output = output.decode(errors="ignore") if output else ""
        logs = self.container.logs().decode()
        self.container.exec_run(["bash", "-c", f"echo '{output}\n{logs}' >> {self.docker_test_dir}/logs/{'new' if self.new else 'old'}.log"])
        return exit_code, output, logs, end-start
    

    def copy_commands_to_container(self, project_root: Path, new_cmd: list[str], old_cmd: list[str]) -> None:
        for i, c in enumerate(new_cmd): 
            if i < 2:
                save = "build"
            else:
                save = "test"
            cmd = ["bash", "-c", f"echo '{c}' >> {self.docker_test_dir}/new_{save}.sh"]
            exit_code, _, _, _ = self.run_command_in_docker(cmd, project_root, check=False, log=False)
            if exit_code != 0:
                logging.error(f"Copying the build and test commands failed with: {exit_code}")
        for i, c in enumerate(old_cmd):
            if i < 2:
                save = "build"
            else:
                save = "test"
            cmd = ["bash", "-c", f"echo '{c}' >> {self.docker_test_dir}/old_{save}.sh"]
            exit_code, _, _, _ = self.run_command_in_docker(cmd, project_root, check=False)
            if exit_code != 0:
                logging.error(f"Copying the build and test commands failed with: {exit_code}")

    def load_docker_image(self, tar_path: Path):
        self.client = docker.from_env()
        with open(tar_path, "rb") as f:
            self.client.images.load(f.read())