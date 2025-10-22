import logging, os
import src.config as conf
from github import Github, Auth
from src.cmake.process import CMakeProcess
from src.cmake.analyzer import CMakeAnalyzer
import docker
from docker.types import Mount

class DockerBuilder:
    def __init__(self, docker_image: str, repo_root: str, test_path: str, flags: list[str], package_manager: str = ""):
        self.client = docker.from_env()
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.repo_root = repo_root
        self.docker_image = docker_image
        self.mounts = [Mount(target="/workspace", source=self.project_root, type="bind", read_only=False)]
        self.container_repo_path = os.path.join("/workspace", os.path.relpath(repo_root, self.project_root))
        self.container_build_path = os.path.join(self.container_repo_path, "build")
        self.test_path = os.path.join(self.container_repo_path, test_path)
        self.flags = flags
        self.package_manager = package_manager
        

    def run(self, test_repeat: int):
        try:
            container = self.client.containers.run(
                self.docker_image,
                command=["sleep", "infinity"],
                mounts=self.mounts,
                working_dir=self.container_repo_path,
                detach=True,
                tty=True
            )
            
            try:
                # Import and run your CMakeProcess in the container
                python_script = f"""
                    import sys
                    sys.path.append('/workspace')
                    from src.cmake.process import CMakeProcess
                    from src.cmake.analyzer import CMakeAnalyzer
                    import os

                    analyzer = CMakeAnalyzer('{self.container_repo_path}')

                    process = CMakeProcess(
                        '{self.container_repo_path}', 
                        build=os.path.join('{self.container_repo_path}', "build"), 
                        test={self.test_path}, 
                        flags={self.flags}, 
                        analyzer=analyzer,
                        package_manager='{self.package_manager}',
                        jobs=4
                    )
                    process.test_path = '{os.path.join(self.container_repo_path, self.test_path)}'

                    if process.build() and process.test([], test_repeat={test_repeat}):
                        print("SUCCESS: Build and test completed")
                        exit(0)
                    else:
                        print("FAILED: Build or test failed")
                        exit(1)
                """
                
                # Execute the Python script in the container
                exit_code, output = container.exec_run(
                    ["python3", "-c", python_script],
                    workdir=self.container_repo_path
                )
                
                logging.info(f"Docker execution output:\n{output.decode()}")
                return exit_code == 0
                
            finally:
                container.stop()
                container.remove()
                
        except Exception as e:
            logging.error(f"Docker operation failed: {e}")
            return False

    def create(self):
        raise NotImplementedError("DockerBuilder create function not implemented yet.")
            # TODO: Generate in Dockerfile:
            # 1. install cmake, ctest, python3 to run this code + others? 
            #       => maybe a base Docker image with all of this already installed
            # 2. with url -> get parent and current commits
            #       => ~ RUN git clone https://github.com/gabime/spdlog /app/spdlog 
            # 3. install parent/current packages => what if there are conflicts? 
            #       => apt-get install packages
            # 4. right before the parent/current test export parent/current_flages
            #       => mkdir build && cd build
            #       => cmake ..
            #       => cmake -LH
            #       => cmake configuration with flags
            #       => cmake build 
            #       => directly from Dockerfile? probably