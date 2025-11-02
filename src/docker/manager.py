import logging, posixpath, docker, os
import src.config as conf
from pathlib import Path
from docker.types import Mount
from typing import Optional

class DockerManager:
    def __init__(self, mount: Path, docker_image: str, docker_test_dir: str, new: bool = False):
        self.mount = mount
        self.docker_image = docker_image
        self.new = new
        self.docker_test_dir = docker_test_dir

    def stop_container(self) -> None:
        if self.container:
            self.container.stop()
            self.container.remove()
            self.container = None

    def start_docker_container(self, container_name: str) -> None:
        client = docker.from_env()
        try:
            try:
                self.container = client.containers.get(container_name)
                logging.info(f"Reusing existing container {container_name}")
                return
            except docker.errors.NotFound: # type: ignore
                pass
            
            mount = Mount(
                target="/workspace", source=str(self.mount), type="bind", read_only=False
            )
            self.container = client.containers.run(
                self.docker_image,
                command=["/bin/bash"],
                name=container_name,
                mounts=[mount],
                working_dir="/workspace",
                detach=True,
                tty=True,
                remove=False,

                cpuset_cpus=conf.resource_limits['cpuset_cpus'],
                mem_limit=conf.resource_limits['mem_limit'],
                #memswap_limit=conf.resource_limits['memswap_limit'],
                cpu_quota=conf.resource_limits['cpu_quota'],
                cpu_period=conf.resource_limits['cpu_period']
            )
            mkdir_cmd = ["mkdir", "-p", f"{self.docker_test_dir}"]
            self.container.exec_run(mkdir_cmd)
            mkdir_cmd = ["mkdir", "-p", f"{self.docker_test_dir}/logs"]
            self.container.exec_run(mkdir_cmd)
            mkdir_cmd = ["mkdir", "-p", f"{self.docker_test_dir}/workspace"]
            self.container.exec_run(mkdir_cmd)
        except Exception as e:
            logging.error(f"Docker execution failed: {e}")

    def run_command_in_docker(self, cmd: list[str], root: Path, workdir: Optional[Path] = None, check: bool = True) -> tuple[int, str, str]:
        rel_root = os.path.relpath(root, self.mount)
        container_root = posixpath.join(f"/workspace", rel_root.replace("\\", "/"))

        if workdir:
            rel_workdir = os.path.relpath(workdir, self.mount).replace("\\", "/")
            container_workdir = posixpath.join(f"/workspace", rel_workdir)
        else:
            container_workdir = container_root
        
        if not self.container:
            logging.error(f"No docker container started")
            return 1, "", ""

        cmd = [str(x) for x in cmd]
        exit_code, output = self.container.exec_run(cmd, workdir=str(container_workdir))
        output = output.decode(errors="ignore") if output else ""
        logs = self.container.logs().decode()
        self.container.exec_run(["bash", "-c", f"echo '{output}\n{logs}' >> {self.docker_test_dir}/logs/{'new' if self.new else 'old'}.log"])
        return exit_code, output, logs
