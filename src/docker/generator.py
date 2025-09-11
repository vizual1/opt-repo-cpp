

class DockerBuilder:
    def __init__(self, file_path: str, repo_urls: list[str], repo_paths: list[str], 
                 flags: set[str], packages: set[str]):
        self.file_path = file_path
        self.repo_urls = repo_urls
        self.repo_paths = repo_paths
        self.flags = flags
        self.packages = packages


    

    