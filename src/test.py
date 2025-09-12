import os, logging
import src.config as conf


class Tester:
    def __init__(self):
        self.storage = conf.storage

    def test(self, inplace: bool = True, url: str = ""):
        return 0

    def test_commit(self, test_path: str):
        return 0