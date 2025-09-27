import logging
import src.config as conf
from src.utils.helper import *
from github import Github, Auth
from src.utils.resolver import *
from src.cmake.process import CMakePackageHandler, CMakeProcess
from src.cmake.analyzer import CMakeAnalyzer

class DockerBuilder:
    def __init__(self):
        raise NotImplementedError("DockerBuilder not implemented.")

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