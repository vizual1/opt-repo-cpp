
from src.config.config import Config
from src.core.docker.tester import DockerTester

class TesterPipeline:
    """
    This class runs the Docker image, evaluates its performance or compares its performance to the mounted project.
    """
    def __init__(self, config: Config):
        self.config = config

    def test(self):
        # TODO: input .tar file or docker image
        file = self.config.input_file
        if file:
            file = self.config.input_file
            names = file.split("_") # owner_repo_patch
            if len(names) != 3:
                raise ValueError(f"Wrong input: {file}, should be 'owner_repo_sha(.tar)'")
            repo_id = f"{names[0]}/{names[1]}"
            repo = self.config.git_client.get_repo(repo_id)
            self.docker = DockerTester(repo, self.config)

            #if file.endswith(".tar"):
            self.docker.test_docker_image()
            

        
