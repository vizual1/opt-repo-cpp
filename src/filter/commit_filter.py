import re, logging, os, json
from github.Commit import Commit
import src.config as conf
from src.filter.llm.prompt import Prompt
from src.filter.llm.openai import OpenRouterLLM
from src.filter.llm.ollama import OllamaLLM
from typing import Optional

class CommitFilter:
    def __init__(self, commit: Commit, filter: str, repo_name: str):
        self.commit = commit
        self.filter = filter
        if conf.llm["ollama"]:
            self.llm = OllamaLLM(conf.llm['ollama_model'])
        else:
            self.llm = OpenRouterLLM(conf.llm['model'])
        self.name = repo_name
        self.config = conf
        self.cache = self._load_cache()

    def accept(self, max_msg_size: int = -1): 
        cached = self.cache.get(self.commit.sha, {}).get(self.filter)
        if cached is not None:
            logging.info(f"Cache hit for {self.commit.sha} ({self.filter}) -> {cached}")
            return cached

        if self.filter == "simple":
            result =  self._simple_filter() and self.cpp_filter()
        elif self.filter == "llm":
            result =  self.cpp_filter() and self._llm_filter(max_msg_size=max_msg_size)
        else:
            result = False

        self._save_cache(self.commit, result)
        return result
    
    def _simple_filter(self) -> bool:
        msg = self.commit.commit.message.lower()
        return any(k in msg for k in ("optimi", "improv"))

    def _llm_filter(self, max_msg_size: int) -> bool:
        msg = self.commit.commit.message
        if max_msg_size != -1 and len(msg) > max_msg_size:
            msg = msg[:max_msg_size] + "..."

        if self.config.llm["twostage"]:
            return self.stage_filter()
        
        p = Prompt([Prompt.Message("user",
            self.config.llm['message2'].replace("<name>", self.name).replace("<message>", self.commit.commit.message)
        )])
        res = self.llm.generate(p)
        logging.info(f"[{self.name}] First LLM returned:\n{res}")

        likelihood = self._extract_likelihood(res)
        if likelihood is None:
            logging.info(f"[{self.name}] Commit {self.commit.sha} did not return a valid likelihood.")
            return False

        if likelihood < self.config.likelihood['min_likelihood']:
            logging.info(f"[{self.name}] Commit {self.commit.sha} has a likelihood of {likelihood}%, which is below the threshold.")
            return False
        if likelihood >= self.config.likelihood['max_likelihood']:
            logging.info(f"[{self.name}] Commit {self.commit.sha} has a high likelihood of being a performance commit ({likelihood}%).")
            return True

        diff = self.get_diff()

        p = Prompt([Prompt.Message("user",
            self.config.llm['message3'].replace("<name>", self.name).replace("<message>", self.commit.commit.message).replace("<diff>", diff)
        )])

        res = self.llm.generate(p)
        logging.info(f"[{self.name}] Second LLM returned:\n{res}")
        return 'YES' in res and 'NO' not in res
    

    def stage_filter(self) -> bool:
        p = Prompt([Prompt.Message("user",
            self.config.llm['message1'].replace("<name>", self.name).replace("<message>", self.commit.commit.message)
        )])

        res = self.llm.generate(p)
        logging.info(f"[{self.name}] First LLM returned: {res}")
        if "YES" in res and not "NO" in res:
            p = Prompt([Prompt.Message("user",
                self.config.llm['message2'].replace("<name>", self.name).replace("<message>", self.commit.commit.message)
            )])

            res = self.llm.generate(p)
            logging.info(f"[{self.name}] Second LLM returned: {res}")
            likelihood = self._extract_likelihood(res)

            if likelihood is None:
                logging.info(f"[{self.name}] Commit {self.commit.sha} did not return a valid likelihood response.")
                return False

            if likelihood < self.config.likelihood['min_likelihood']:
                logging.info(f"[{self.name}] Commit {self.commit.sha} has a likelihood of {likelihood}%, which is below the threshold.")
                return False
            if likelihood >= self.config.likelihood['max_likelihood']:
                logging.info(f"[{self.name}] Commit {self.commit.sha} has a high likelihood of being a performance commit ({likelihood}%).")
                return True
            
        return False
    
    def _extract_likelihood(self, text: str) -> Optional[float]:
        match = re.search(r"likelihood\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)%?", text, flags=re.IGNORECASE)
        return float(match.group(1)) if match else None
    
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
        ignore_dirs = ("third_party", "vendor", "external")
        for f in self.commit.files:
            if f.filename.endswith(cpp_extensions) and not any(d in f.filename for d in ignore_dirs):
                return True
        return False
    
    # TODO: test
    def _save_cache(self, commit: Commit, decision: bool) -> None:
        self.cache[commit.sha] = {self.filter: decision}
        try:
            with open(self.config.llm['cache_file'], "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logging.warning(f"Failed to write cache: {e}")

    def _load_cache(self) -> dict:
        if os.path.exists(self.config.llm['cache_file']):
            try:
                with open(self.config.llm['cache_file'], "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}