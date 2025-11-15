import logging, posixpath, docker, os
import src.config as conf
from pathlib import Path
from docker.types import Mount
from typing import Optional
from src.config.config import Config

class DockerManager:
    def __init__(self, config: Config, mount: Path, docker_image: str, docker_test_dir: str, new: bool = False):
        self.config = config
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
            
            logging.info(f"Run docker image ({self.docker_image}) mounted on {str(self.mount)}.")
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

                cpuset_cpus=self.config.resources.cpuset_cpus,
                mem_limit=self.config.resources.mem_limit,
                #memswap_limit=conf.resource_limits['memswap_limit'],
                cpu_quota=self.config.resources.cpu_quota,
                cpu_period=self.config.resources.cpu_period
            )
            mkdir_cmd = ["mkdir", "-p", f"{self.docker_test_dir}"]
            self.container.exec_run(mkdir_cmd)
            mkdir_cmd = ["mkdir", "-p", f"{self.docker_test_dir}/logs"]
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
    

    def copy_commands_to_container(self, project_root: Path, new_cmd: list[str], old_cmd: list[str]) -> None:
        for i, c in enumerate(new_cmd): 
            if i < 2:
                save = "build"
            else:
                save = "test"
            cmd = ["bash", "-c", f"echo '{c}' >> {self.docker_test_dir}/new_{save}.sh"]
            exit_code, _, _ = self.run_command_in_docker(cmd, project_root, check=False)
            if exit_code != 0:
                logging.error(f"Copying the build and test commands failed with: {exit_code}")
        for i, c in enumerate(old_cmd):
            if i < 2:
                save = "build"
            else:
                save = "test"
            cmd = ["bash", "-c", f"echo '{c}' >> {self.docker_test_dir}/old_{save}.sh"]
            exit_code, _, _ = self.run_command_in_docker(cmd, project_root, check=False)
            if exit_code != 0:
                logging.error(f"Copying the build and test commands failed with: {exit_code}")