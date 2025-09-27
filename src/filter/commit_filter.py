import re, logging
from github.Commit import Commit
import src.config as conf
from src.filter.llm.prompt import Prompt
from src.filter.llm.openai import OpenRouterLLM

class CommitFilter:
    def __init__(self, commit: Commit, filter: str, repo_name: str):
        self.commit = commit
        self.filter = filter
        self.llm = OpenRouterLLM(conf.llm['model'])
        self.name = repo_name
        #self.cache = self._load_cache()

    def accept(self): 
        if self.filter == "simple":
            return self._simple_filter() and self.test_filter() and self.cpp_filter()
        elif self.filter == "llm":
            return self._llm_filter() and self.test_filter() and self.cpp_filter()
        return True
    
    def _simple_filter(self) -> bool:
        msg = self.commit.commit.message
        if "optimi" in msg:
            return True
        elif "improv" in msg:
            return True
        return False

    def _llm_filter(self) -> bool:
        p = Prompt([Prompt.Message("user",
                                    f"The following is the message of a commit in the {self.name} repository:\n\n###Message Start###{self.commit.commit.message}\n###Message End###"
                                    + f"\n\nHow likely is it for this commit to be a performance improving commit in terms of execution time? Answer by only writing the likelihood in the following format:\nLikelihood: x%"
                                    )])
        res = self.llm.generate(p)

        match = re.search(r"Likelihood:\s*([0-9]+(?:\.[0-9]+)?)%", res)
        if match:
            likelihood = float(match.group(1))
        else:
            logging.info(f"Commit {self.commit.sha} in {self.name} did not return a valid likelihood response.")
            return False

        if likelihood < conf.likelihood['min_likelihood']:
            logging.info(f"Commit {self.commit.sha} in {self.name} has a likelihood of {likelihood}%, which is below the threshold.")
            return False
        if likelihood >= conf.likelihood['max_likelihood']:
            logging.info(f"Commit {self.commit.sha} in {self.name} has a high likelihood of being a performance commit ({likelihood}%).")
            return True

        """
        diff = self.get_diff(commit)

        # Second stage, ask O4
        p = Prompt([Prompt.Message("user",
                                    f"The following is the message of a commit in the {repo.full_name} repository:\n\n###Message Start###{commit.commit.message}\n###Message End###"
                                    + f"\n\nThe diff of the commit is:\n\n###Diff Start###{diff}\n###Diff End###"
                                    + f"\n\nIs this commit a performance improving commit in terms of execution time? Answer with 'YES' or 'NO'."
                                    )])

        tokens_cnt = len(tiktoken.encoding_for_model("o3").encode(p.messages[0].content))

        if tokens_cnt > conf.llm['max-o4-tokens']:
            logging.info(f"Commit {commit.sha} in {repo.full_name} has too many tokens ({tokens_cnt}), skipping.")
            return False

        res = self.o4.get_response(p)
        """
        return 'YES' in res and 'NO' not in res

    def test_filter(self) -> bool:
        """
        Returns True if the commit does NOT touch test files.
        """
        for f in self.commit.files:
            file_path = f.filename
            if any(file_path.startswith(dir) for dir in conf.TEST_DIR):
                return False
        return True

    def cpp_filter(self) -> bool:
        """
        Returns True if the commit modifies any C++ source or header files.
        """
        cpp_extensions = (".cpp", ".cc", ".cxx", ".c++", ".h", ".hpp")
        
        for f in self.commit.files:
            if f.filename.endswith(cpp_extensions):
                return True
        return False
    
    # TODO: write save_cache/load_cache and test it
    def _save_cache(self, commit: Commit) -> None:
        self.cache[commit.sha] = {} # TODO: add commit information to cache
        # TODO: write the cache to memory
        return
    
    def _load_cache(self) -> str:
        if not self.cache:
            self.cache = {} # TODO: load the cache from outside
        elif self.commit.sha in self.cache.keys():
            if self.filter in self.cache[self.commit.sha]:
                return self.cache[self.commit.sha][self.filter]
        return ""