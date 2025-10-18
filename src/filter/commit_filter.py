import re, logging
from github.Commit import Commit
import src.config as conf
from src.filter.llm.prompt import Prompt
from src.filter.llm.openai import OpenRouterLLM
from src.filter.llm.ollama import OllamaLLM

class CommitFilter:
    def __init__(self, commit: Commit, filter: str, repo_name: str):
        self.commit = commit
        self.filter = filter
        if conf.llm["ollama"]:
            self.llm = OllamaLLM(conf.llm['ollama_model'])
        else:
            self.llm = OpenRouterLLM(conf.llm['model'])
        self.name = repo_name
        #self.cache = self._load_cache()

    def accept(self, max_msg_size: int = 200): 
        if self.filter == "simple":
            return self._simple_filter() and self.cpp_filter()
        elif self.filter == "llm":
            return self.cpp_filter() and self._llm_filter(max_msg_size=max_msg_size)
        return False
    
    def _simple_filter(self) -> bool:
        msg = self.commit.commit.message
        if "optimi" in msg:
            return True
        elif "improv" in msg:
            return True
        return False

    def _llm_filter(self, max_msg_size: int) -> bool:
        if conf.llm["twostage"]:
            return self.stage_filter()
        
        p = Prompt([Prompt.Message("user",
            conf.llm['message2'].replace("<name>", self.name).replace("<message>", self.commit.commit.message)
        )])
        res = self.llm.generate(p)
        logging.info(f"First LLM returned:\n{res}")

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

        diff = self.get_diff()

        p = Prompt([Prompt.Message("user",
            conf.llm['message3'].replace("<name>", self.name).replace("<message>", self.commit.commit.message).replace("<diff>", diff)
        )])

        res = OllamaLLM(conf.llm['ollama_model']).generate(p)
        logging.info(f"Second LLM returned:\n{res}")

        return 'YES' in res and 'NO' not in res
    

    def stage_filter(self) -> bool:
        p = Prompt([Prompt.Message("user",
            conf.llm['message1'].replace("<name>", self.name).replace("<message>", self.commit.commit.message)
        )])

        res = self.llm.generate(p)
        logging.info(f"First LLM returned: {res}")
        if "yes" in res.lower():
            p = Prompt([Prompt.Message("user",
                conf.llm['message2'].replace("<name>", self.name).replace("<message>", self.commit.commit.message)
            )])

            res = self.llm.generate(p)
            logging.info(f"Second LLM returned: {res}")
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
            
        return False
    
    def get_diff(self) -> str:
        diff = ""
        for f in self.commit.files:
            if f.patch:
                diff += f"--- {f.filename}\n"
                diff += f.patch + '\n'
        return diff

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
    # write the cache to memory
    # add commit information to cache
    # load the cache from outside
    def _save_cache(self, commit: Commit) -> None:
        self.cache[commit.sha] = {}
        return
    
    def _load_cache(self) -> str:
        if not self.cache:
            self.cache = {} 
        elif self.commit.sha in self.cache.keys():
            if self.filter in self.cache[self.commit.sha]:
                return self.cache[self.commit.sha][self.filter]
        return ""