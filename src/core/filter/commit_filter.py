import re, logging, os, json
from github.Commit import Commit
from github.Repository import Repository
from src.llm.prompt import Prompt
from src.llm.openai import OpenRouterLLM
from src.llm.ollama import OllamaLLM
from typing import Optional
from src.config.config import Config
from github.GithubException import UnknownObjectException

perf_label_keywords = {
    'performance', 'perf', 'optimization', 'optimisation', 'optimize', 'optimize',
    'speed', 'latency', 'throughput', 'regression: performance', 'perf regression',
    'slow', 'slowness', 'timeout', 'benchmark', 'hot path', 'hotpath', 'cpu', 'gc',
    'jmh', 'efficiency'
}
perf_text_keywords = {
    'performance', 'perf', 'optimiz', 'speed', 'latency', 'throughput',
    'slow', 'slowness', 'timeout', 'hang', 'stall', 'regression', 'benchmark',
    'hot path', 'hotpath', 'cpu', 'allocation', 'alloc', 'gc', 'jmh', 'efficiency',
    'big-o', 'complexity'
}
runtime_hint_keywords = {
    'latency', 'throughput', 'slow', 'slowness', 'timeout', 'hang', 'stall', 'cpu', 
    'jmh', 'benchmark', 'regression'
}

class CommitFilter:
    def __init__(self, commit: Commit, config: Config, repo: Repository):
        self.commit = commit
        self.config = config
        self.llm1 = OpenRouterLLM(self.config, self.config.llm.model1)
        self.llm2 = OpenRouterLLM(self.config, self.config.llm.model2)
        self.repo = repo
        self.cache: dict[str, dict[str, dict[str, bool]]] = self._load_cache()

    def accept(self, max_msg_size: int = -1) -> bool: 
        logging.info(f"[{self.repo.full_name}] ({self.commit.sha}) Filtering...")
        name = self.config.llm.ollama_stage1_model + "_" + self.config.llm.ollama_stage2_model if self.config.llm.ollama_enabled else self.config.llm.model1 + "_" + self.config.llm.model2
        cached = self.cache.get(self.repo.full_name, {}).get(self.config.filter_type + (f"_{name}" if self.config.filter_type == "llm" else ""), {}).get(self.commit.sha)
        if cached is not None:
            logging.info(f"Cache hit for {self.commit.sha} ({self.config.filter_type}) -> {cached}")
            return cached

        if self.config.filter_type == "simple":
            result = self._simple_filter() and self._only_cpp_source_modified()
            self._save_cache(self.commit, result)
        elif self.config.filter_type == "llm":
            result = self._only_cpp_source_modified() and self._llm_filter(max_msg_size=max_msg_size) 
            self._save_cache(self.commit, result, extra=f"_{name}")
        elif self.config.filter_type == "issue":
            result = self._only_cpp_source_modified() and self.fixed_performance_issue() is not None
            self._save_cache(self.commit, result, extra=f"_{name}")
        else:
            result = False

        return result
    
    def _simple_filter(self) -> bool:
        msg = self.commit.commit.message.lower()
        return any(k in msg for k in perf_label_keywords | perf_text_keywords | runtime_hint_keywords)

    def _llm_filter(self, max_msg_size: int) -> bool:

        if self.fixed_performance_issue():
            return True

        msg = self.commit.commit.message
        if max_msg_size != -1 and len(msg) > max_msg_size:
            msg = msg[:max_msg_size] + "..."
        
        """
        p = Prompt([Prompt.Message("user",
            (self.config.llm['stage1']
                .replace("<name>", self.repo.full_name)
                .replace("<message>", self.commit.commit.message)
            )
        )])
        """
        diff = self.get_diff()

        p = Prompt([
            Prompt.Message("system", 
                "You are a strict binary classifier. "
                "Determine if the commit improves runtime performance (e.g., reduces CPU usage, improves memory efficiency, speeds up execution). "
                "Do not count bug fixes, correctness changes, refactoring, or style cleanups as performance improvements. "
                "Respond ONLY in this JSON format: {\"answer\": \"yes\"} or {\"answer\": \"no\"}. "
                "If you do not have enough information to decide, say {\"answer\": \"maybe\"}."
                "Do not add any explanation or commentary."),
            Prompt.Message("user",
                (self.config.stage1_prompt
                    .replace("<name>", self.repo.full_name)
                    .replace("<message>", self.commit.commit.message)
                    .replace("<diff>", diff))
        )])

        if self.config.llm.ollama_enabled:
            self.llm = OllamaLLM(self.config, self.config.llm.ollama_stage1_model)
        logging.info(f"[{self.repo.full_name}] First LLM prompt: {p.messages[1].content}")
        res = self.llm.generate(p)
        logging.info(f"[{self.repo.full_name}] First LLM returned: {res}")
        
        #if 'maybe' in res.lower():
            #

        if 'yes' in res.lower():
            """
            likelihood = self._extract_likelihood(res)
            if likelihood is None:
                logging.info(f"[{self.repo.full_name}] Commit {self.commit.sha} did not return a valid likelihood.")
                return False

            if likelihood < self.config.likelihood['min_likelihood']:
                logging.info(f"[{self.repo.full_name}] Commit {self.commit.sha} has a likelihood of {likelihood}%, which is below the threshold.")
                return False
            if likelihood >= self.config.likelihood['max_likelihood']:
                logging.info(f"[{self.repo.full_name}] Commit {self.commit.sha} has a high likelihood of being a performance commit ({likelihood}%).")
                return True
            """

            p = Prompt([
                Prompt.Message("system", 
                    "You are a strict binary classifier. "
                    "Determine if the commit improves runtime performance (e.g., reduces CPU usage, improves memory efficiency, speeds up execution). "
                    "Do not count bug fixes, correctness changes, refactoring, or style cleanups as performance improvements. "
                    "Respond ONLY in this JSON format: {\"answer\": \"yes\"} or {\"answer\": \"no\"}. "
                    "If you do not have enough information to decide, say {\"answer\": \"no\"}."
                    "Do not add any explanation or commentary."),
                Prompt.Message("user",
                    (self.config.stage2_prompt
                        .replace("<name>", self.repo.full_name)
                        .replace("<message>", self.commit.commit.message)
                        .replace("<diff>", diff))
            )])

            if self.config.llm.ollama_enabled:
                self.llm = OllamaLLM(self.config, self.config.llm.ollama_stage2_model)
            logging.info(f"[{self.repo.full_name}] Second LLM prompt: {p.messages[1].content}")
            res = self.llm.generate(p)
            logging.info(f"[{self.repo.full_name}] Second LLM returned: {res}")
            if 'yes' in res.lower():
                return True
            
        return False
    
    def _extract_likelihood(self, text: str) -> Optional[float]:
        match = re.search(r"likelihood\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)%?", text, flags=re.IGNORECASE)
        return float(match.group(1)) if match else None
    
    def get_diff(self) -> str:
        diff_lines: list[str] = []
        for f in self.commit.files:
            if f.patch:
                diff_lines.append(f"--- {f.filename}")
                patch = f.patch
                if len(patch) > 8000:
                    diff_lines.append("\n... [diff truncated] ...")
                    break
                diff_lines.append(patch)
        return "\n".join(diff_lines)

    def _modify_cpp_filter(self) -> bool:
        """Returns True if the commit modifies any C++ source or header files."""
        cpp_extensions = (".cpp", ".cc", ".cxx", ".c++", ".h", ".hpp")
        ignore_dirs = ("third_party", "vendor", "external")
        for f in self.commit.files:
            if f.filename.endswith(cpp_extensions) and not any(d in f.filename for d in ignore_dirs):
                return True
        return False
    
    def _only_cpp_source_modified(self) -> bool:
        """Return True if commit modifies only C++ source/header files (no tests, no non-source)."""
        cpp_extensions = (".cpp", ".cc", ".cxx", ".c++", ".h", ".hpp")
        ignore_dirs = ("third_party", "vendor", "external")

        for f in self.commit.files:
            filename = f.filename
            if any(d in filename for d in ignore_dirs):
                continue

            if not filename.endswith(cpp_extensions):
                logging.info(f"[{self.repo.full_name}] Commit {self.commit.sha} changes a non-source file: {filename}.")
                return False
            
            if any(filename.startswith(tdir) for tdir in self.config.valid_test_dirs):
                logging.info(f"[{self.repo.full_name}] Commit {self.commit.sha} changes a test file: {filename}")
                return False
            
        return True
    
    def _modify_test_filter(self) -> bool:
        """Check whether a commit has modified a file in test directories."""
        for f in self.commit.files:
            for tdir in self.config.valid_test_dirs:
                if f.filename.startswith(tdir) or tdir in f.filename:
                    return True
        return False
    
    def _save_cache(self, commit: Commit, decision: bool, extra: str = "") -> None:
        repo_name = self.repo.full_name
        filter_type = self.config.filter_type + extra

        if repo_name not in self.cache:
            self.cache[repo_name] = {}
        if filter_type not in self.cache[repo_name]:
            self.cache[repo_name][filter_type] = {}
        self.cache[repo_name][filter_type][self.commit.sha] = decision

        try:
            with open(self.config.llm.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logging.warning(f"Failed to write cache: {e}")

    def _load_cache(self) -> dict[str, dict[str, dict[str, bool]]]:
        path = self.config.llm.cache_file
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def extract_fixed_issues(self) -> dict[int, str]:
        """
        Extract issue numbers from commit message that are explicitly closed/fixed.
        
        Args:
            commit_message: The commit message to parse
            repo: The GitHub repository object
            
        Returns:
            Set of issue numbers that are explicitly closed by this commit
            
        Examples:
            - "Fixes #123" -> {123}
            - "Closes #456 and resolves #789" -> {456, 789}
            - "Fix GH-123" -> {123}
            - "Resolves owner/repo#456" -> {456} (if matches current repo)
        """
        commit_message = self.commit.commit.message
        if not commit_message:
            return {}
            
        msg = commit_message.strip()
        results: dict[int, str] = {}

        # Enhanced regex patterns to catch more formats
        closing_prefix = r'(?:(?<![A-Za-z])(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved|address|addresses|addressed))(?:\s*[:\-])?\s+'
        
        # Individual issue reference patterns (without named groups to avoid conflicts)
        issue_patterns = [
            r'#(\d+)',  # #123
            r'GH-(\d+)',  # GH-123
            r'issue\s*#(\d+)',  # issue #123
            r'bug\s*#(\d+)',  # bug #123
        ]
        
        # Full repository reference patterns
        full_repo_patterns = [
            r'([\w.-]+/[\w.-]+)#(\d+)',  # owner/repo#123
            r'https?://github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)',  # Full URL
        ]
        
        # PR patterns (to be filtered out)
        pr_patterns = [
            r'https?://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)',  # PR URL
        ]
        
        # Compile all patterns
        all_issue_patterns = issue_patterns + full_repo_patterns
        compiled_issue_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in all_issue_patterns]
        compiled_pr_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in pr_patterns]
        
        # Main fix block pattern (simplified to avoid group conflicts)
        fix_block = re.compile(
            closing_prefix + r'(?:' + '|'.join(all_issue_patterns) + r')(?:\s*(?:,|\band\b|&|\bor\b|\|)\s*(?:' + '|'.join(all_issue_patterns) + r'))*', 
            re.IGNORECASE | re.MULTILINE
        )

        issue_cache = {}
        
        def get_ref_type(n: int) -> str:
            """Return 'issue', 'pull_request', or 'unknown'."""
            if n in issue_cache:
                return issue_cache[n]
            try:
                issue = self.repo.get_issue(n)
                ref_type = "issue" if getattr(issue, "pull_request", None) is None else "pull_request"
                issue_cache[n] = ref_type
                return ref_type
            except UnknownObjectException:
                issue_cache[n] = "unknown"
                return "unknown"
            except Exception as e:
                logging.warning(f"Error checking issue #{n} in {self.repo.full_name}: {e}")
                issue_cache[n] = "unknown"
                return "unknown"

        try:
            for block in fix_block.finditer(msg):
                block_text = block.group(0)
                logging.info(f"Found fix block: '{block_text}'")

                # Extract PR references first
                for pr_pattern in compiled_pr_patterns:
                    for match in pr_pattern.finditer(block_text):
                        repo_name = match.group(1)
                        number = int(match.group(2))
                        if repo_name.lower() == self.repo.full_name.lower():
                            results[number] = "pull_request"
                            logging.info(f"Found PR reference: {repo_name}#{number}")

                # Extract issue references
                for pattern in compiled_issue_patterns:
                    for match in pattern.finditer(block_text):
                        issue_number = None

                        if len(match.groups()) == 1:
                            issue_number = int(match.group(1))
                        elif len(match.groups()) == 2:
                            repo_name = match.group(1)
                            if repo_name.lower() == self.repo.full_name.lower():
                                issue_number = int(match.group(2))

                        if issue_number:
                            ref_type = get_ref_type(issue_number)
                            if ref_type in ("issue", "pull_request"):
                                results[issue_number] = ref_type
                                logging.info(f"Found {ref_type} reference: #{issue_number}")

        except Exception as e:
            logging.error(f"Error parsing commit message for issues: {e}")
            return results

        return results


    def fixed_performance_issue(self) -> Optional[int]:
        msg = self.commit.commit.message or ""
        refs = self.extract_fixed_issues()
        if not refs:
            return None

        issue_title_body_tuples = []
        for number, ref_type in refs.items():
            try:
                gh_issue = self.repo.get_issue(number)

                title = gh_issue.title or ""
                body = gh_issue.body or ""
                issue_title_body_tuples.append((number, title, body))

                ref_type = ref_type.replace('_', ' ')
                p = Prompt(messages=[
                    Prompt.Message("system", 
                        "You are a strict binary classifier. "
                        "Determine if the commit improves runtime performance (e.g., reduces CPU usage, improves memory efficiency, speeds up execution). "
                        "Do not count bug fixes, correctness changes, refactoring, or style cleanups as performance improvements. "
                        "Respond ONLY in this JSON format: {\"answer\": \"yes\"} or {\"answer\": \"no\"}. "
                        "If you do not have enough information to decide, say {\"answer\": \"no\"}."
                        "Do not add any explanation or commentary."),
                    Prompt.Message("user",
                        f"The following is a {ref_type} in the {self.repo.full_name} repository:\n\n"
                        f"###{ref_type} Title###{title}\n###{ref_type} Title End###\n\n"
                        f"###{ref_type} Body###{body}\n###{ref_type} Body End###\n\n"
                        f"The following is the commit message that fixes this {ref_type}:\n\n"
                        f"###Commit Message###{msg}\n###Commit Message End###\n\n"
                        f"Answer strictly in this JSON format (do not add any explanation):\n"
                        f"{{\"answer\": \"yes\"}} or {{\"answer\": \"no\"}}.\n\n"
                        f"Question: Is this issue likely related to improving execution time?"
                )])
                if self.config.llm.ollama_enabled:
                    self.llm1 = OllamaLLM(self.config, self.config.llm.ollama_stage1_model)
                logging.info(f"First LLM issue prompt: {p.messages[1].content}")
                res = self.llm1.generate(p)
                logging.info(f"First LLM issue response: {res}")

                if "yes" in res.lower().strip():
                    logging.info(f"Commit {self.commit.sha} in {self.repo.full_name} is related to a likely performance issue (#{number}).")

                    p = Prompt(messages=[
                        Prompt.Message("system", 
                            "You are a strict binary classifier. "
                            "Determine if the commit improves runtime performance (e.g., reduces CPU usage, improves memory efficiency, speeds up execution). "
                            "Do not count bug fixes, correctness changes, refactoring, or style cleanups as performance improvements. "
                            "Respond ONLY in this JSON format: {\"answer\": \"yes\"} or {\"answer\": \"no\"}. "
                            "If you do not have enough information to decide, say {\"answer\": \"no\"}."
                            "Do not add any explanation or commentary."),
                        Prompt.Message("user",
                            f"The following is a {ref_type} in the {self.repo.full_name} repository:\n\n"
                            f"###{ref_type} Title###{title}\n###{ref_type} Title End###\n\n"
                            f"###{ref_type} Body###{body}\n###{ref_type} Body End###\n\n"
                            f"The following is the commit message that fixes this {ref_type}:\n\n"
                            f"###Commit Message###{msg}\n###Commit Message End###\n\n"
                            f"Answer strictly in this JSON format (do not add any explanation):\n"
                            f"{{\"answer\": \"yes\"}} or {{\"answer\": \"no\"}}.\n\n"
                            f"Question: Is this issue likely related to improving execution time?"
                    )])
                    if self.config.llm.ollama_enabled:
                        self.llm2 = OllamaLLM(self.config, self.config.llm.ollama_stage2_model)
                    logging.info(f"Second LLM issue prompt: {p.messages[1].content}")
                    res = self.llm2.generate(p)
                    logging.info(f"Second LLM issue response: {res}")

                    if "yes" in res.lower().strip():
                        logging.info(f"Commit {self.commit.sha} in {self.repo.full_name} is related to a likely performance issue (#{number}).")
                        return number

            except UnknownObjectException:
                continue
            
        logging.info(f"Commit {self.commit.sha} in {self.repo.full_name} is not fixing performance issues.")
        return None
