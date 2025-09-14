import logging

class Statistics:
    def __init__(self):
        self.num_commits = 0
        self.perf_commits = 0
        self.lines_added = 0
        self.lines_deleted = 0

    def write_final_log(self):
        logging.info(f"Number of commits: {self.num_commits}")
        logging.info(f"Number of filtered commits: {self.perf_commits}")
        logging.info(f"Optimization Ratio: {self.perf_commits/self.num_commits}")
        logging.info(f"Number of lines added: {self.lines_added}")
        logging.info(f"Number of lines deleted: {self.lines_deleted}")
        logging.info(f"Number of lines changed: {self.lines_added + self.lines_deleted}")
        logging.info(f"Average number of lines added: {self.lines_added/self.perf_commits}")
        logging.info(f"Average number of lines deleted: {self.lines_deleted/self.perf_commits}")
        logging.info(f"Average number of lines changed: {(self.lines_added + self.lines_deleted)/self.perf_commits}")
    