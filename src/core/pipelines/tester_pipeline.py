
from src.config.config import Config
from src.core.docker.tester import DockerTester

class TesterPipeline:
    """
    This class runs the Docker image, evaluates its performance or compares its performance to the mounted project.
    """
    def __init__(self, config: Config):
        self.config = config
        self.docker = DockerTester(self.config)

    def test(self):
        # TODO
        if self.config.input_file:
            self.docker.test_input_folder()
        
        if self.config.docker_image and self.config.mount_path:
            self.docker.test_mounted_against_docker(self.config.docker_image, self.config.mount_path)

        