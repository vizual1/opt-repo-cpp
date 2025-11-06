import re, logging, os, json
from github.Commit import Commit
from github.Repository import Repository
from src.llm.prompt import Prompt
from src.llm.openai import OpenRouterLLM
from src.llm.ollama import OllamaLLM
from typing import Optional
from src.utils.config import Config
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
# We treat memory-only topics as weak signal; some memory changes impact runtime,
# but to stay faithful to "execution time", we require at least one runtime-ish term.
runtime_hint_keywords = {'latency', 'throughput', 'slow', 'slowness', 'timeout', 'hang', 'stall', 'cpu', 'jmh', 'benchmark', 'regression'}

class CommitFilter:
    def __init__(self, commit: Commit, config: Config, repo: Repository):
        self.commit = commit
        self.config = config
        self.llm = OpenRouterLLM(self.config.llm['model'])
        self.repo = repo
        self.cache: dict[str, dict[str, dict[str, bool]]] = self._load_cache()

    def accept(self, max_msg_size: int = -1) -> bool: 
        logging.info(f"[{self.repo.full_name}] ({self.commit.sha}) Filtering...")
        name = self.config.llm['ollama_stage1_model'] + "_" + self.config.llm['ollama_stage2_model'] if self.config.llm['ollama'] else self.config.llm['model']
        cached = self.cache.get(self.repo.full_name, {}).get(self.config.filter + (f"_{name}" if self.config.filter == "llm" else ""), {}).get(self.commit.sha)
        if cached is not None:
            logging.info(f"Cache hit for {self.commit.sha} ({self.config.filter}) -> {cached}")
            return cached

        if self.config.filter == "simple":
            result = (self._simple_filter() or self._performance_issue_commit_filter()) and self._only_cpp_source_modified()
            self._save_cache(self.commit, result)
        elif self.config.filter == "llm":
            result = self._only_cpp_source_modified() and self.fixed_performance_issue() is not None #(self._performance_issue_commit_filter() or self._llm_filter(max_msg_size=max_msg_size))
            self._save_cache(self.commit, result, extra=f"_{name}")
        else:
            result = False

        return result
    
    def _simple_filter(self) -> bool:
        msg = self.commit.commit.message.lower()
        return any(k in msg for k in perf_label_keywords | perf_text_keywords | runtime_hint_keywords)

    def _llm_filter(self, max_msg_size: int) -> bool:
        msg = self.commit.commit.message
        if max_msg_size != -1 and len(msg) > max_msg_size:
            msg = msg[:max_msg_size] + "..."
        
        p = Prompt([Prompt.Message("user",
            (self.config.llm['stage1']
                .replace("<name>", self.repo.full_name)
                .replace("<message>", self.commit.commit.message)
            )
        )])

        if self.config.llm["ollama"]:
            self.llm = OllamaLLM(self.config.llm['ollama_stage1_model'])
        res = self.llm.generate(p)
        logging.info(f"[{self.repo.full_name}] First LLM returned:\n{res}")

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

        diff = self.get_diff()

        p = Prompt([Prompt.Message("user",
            (self.config.llm['stage2']
                .replace("<name>", self.repo.full_name)
                .replace("<message>", self.commit.commit.message)
                .replace("<diff>", diff)
            )
        )])

        if self.config.llm["ollama"]:
            self.llm = OllamaLLM(self.config.llm['ollama_stage2_model'])
        res = self.llm.generate(p)
        logging.info(f"[{self.repo.full_name}] Second LLM returned:\n{res}")
        return 'YES' in res and 'NO' not in res
    
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
            
            if any(filename.startswith(tdir) for tdir in self.config.valid_test_dir):
                logging.info(f"[{self.repo.full_name}] Commit {self.commit.sha} changes a test file: {filename}")
                return False
            
        return True
    
    def _modify_test_filter(self) -> bool:
        """Check whether a commit has modified a file in test directories."""
        for f in self.commit.files:
            for tdir in self.config.valid_test_dir:
                if f.filename.startswith(tdir):
                    return True
        return False
    
    def _save_cache(self, commit: Commit, decision: bool, extra: str = "") -> None:
        repo_name = self.repo.full_name
        filter_type = self.config.filter + extra

        if repo_name not in self.cache:
            self.cache[repo_name] = {}
        if filter_type not in self.cache[repo_name]:
            self.cache[repo_name][filter_type] = {}
        self.cache[repo_name][filter_type][self.commit.sha] = decision

        try:
            with open(self.config.llm['cache_file'], "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logging.warning(f"Failed to write cache: {e}")

    def _load_cache(self) -> dict[str, dict[str, dict[str, bool]]]:
        path = self.config.llm['cache_file']
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def _performance_issue_commit_filter(self) -> bool:
        """
        Heuristic: A commit is considered "linked to a performance issue" iff the commit
        message references at least one GitHub issue/PR whose labels/title/body indicate
        an execution-time performance topic.
        """
        msg = self.commit.commit.message or ""

        # --- 1) Extract referenced issues/PRs from the commit message
        # Patterns:
        #   #123
        #   owner/repo#123
        #   https://github.com/owner/repo/issues/123
        #   https://github.com/owner/repo/pull/123
        issue_refs = set()

        # same-repo short refs: #123
        for m in re.finditer(r'(?<![\w/])#(\d+)\b', msg):
            issue_refs.add((self.repo.full_name, int(m.group(1))))

        # cross-repo short refs: owner/repo#123
        for m in re.finditer(r'([\w.-]+/[\w.-]+)#(\d+)\b', msg):
            issue_refs.add((m.group(1), int(m.group(2))))

        # full URLs
        for m in re.finditer(
            r'https?://github\.com/([\w.-]+/[\w.-]+)/(?:issues|pull)/(\d+)',
            msg, flags=re.IGNORECASE
        ):
            issue_refs.add((m.group(1), int(m.group(2))))

        if not issue_refs:
            return False  # Not "linked to an issue" at all

        def text_has_perf(text: str) -> bool:
            t = (text or "").lower()
            has_core = any(k in t for k in perf_text_keywords)
            has_runtime_hint = any(k in t for k in runtime_hint_keywords)
            return has_core and has_runtime_hint

        if issue_refs:
            logging.info(f"[{self.repo.full_name}] ({self.commit.sha}) issue references found {issue_refs}")

        # --- 3) Resolve and evaluate each referenced issue/PR
        for full_repo_name, number in issue_refs:
            try:
                target_repo = self.config.git.get_repo(full_repo_name) if full_repo_name != self.repo.full_name else self.repo

                # Try as Issue (works for PRs too in GitHub's model)
                gh_issue = target_repo.get_issue(number)
                title = gh_issue.title or ""
                body = gh_issue.body or ""
                labels = {lbl.name.lower() for lbl in gh_issue.labels}
                
                # Check labels first (cheap & strong signal)
                if any(any(k in lbl for k in perf_label_keywords) for lbl in labels):
                    return True

                # Fall back to text scan of title/body
                if text_has_perf(title) or text_has_perf(body):
                    return True

                # If it is actually a PR, scan PR body too (may differ from issue body)
                if gh_issue.pull_request is not None:
                    try:
                        pr = target_repo.get_pull(number)
                        pr_title = pr.title or ""
                        pr_body = pr.body or ""
                        pr_labels = {lbl.name.lower() for lbl in pr.labels}
                        if any(any(k in lbl for k in perf_label_keywords) for lbl in pr_labels):
                            return True
                        if text_has_perf(pr_title) or text_has_perf(pr_body):
                            return True
                    except Exception:
                        # Ignore PR fetch failures; continue checking others
                        pass

            except Exception:
                # Be resilient to transient API hiccups; don't fail the whole run
                continue

        # None of the linked issues/PRs look performance-related
        return False
    
    def extract_fixed_issues(self) -> set[int]:
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
            return set()
            
        msg = commit_message.strip()
        out: set[int] = set()

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
        compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in all_issue_patterns]
        compiled_pr_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in pr_patterns]
        
        # Main fix block pattern (simplified to avoid group conflicts)
        fix_block = re.compile(
            closing_prefix + r'(?:' + '|'.join(all_issue_patterns) + r')(?:\s*(?:,|\band\b|&|\bor\b|\|)\s*(?:' + '|'.join(all_issue_patterns) + r'))*', 
            re.IGNORECASE | re.MULTILINE
        )

        # Cache for API calls to avoid duplicate requests
        issue_cache = {}
        
        def is_issue(n: int) -> bool:
            """Check if the number refers to an issue (not a PR)."""
            # Check cache first
            if n in issue_cache:
                return issue_cache[n]
                
            try:
                issue = self.repo.get_issue(n)
                is_issue_result = getattr(issue, "pull_request", None) is None
                issue_cache[n] = is_issue_result
                return is_issue_result
            except UnknownObjectException:
                # Issue doesn't exist or is private
                issue_cache[n] = False
                return False
            except Exception as e:
                # Handle rate limiting and other API errors
                logging.warning(f"Error checking issue #{n} in {self.repo.full_name}: {e}")
                issue_cache[n] = False  # Assume it's an issue to be safe
                return False

        try:
            # Find all fix blocks in the commit message
            for block in fix_block.finditer(msg):
                block_text = block.group(0)
                logging.debug(f"Found fix block: '{block_text}'")
                
                # Extract issue references using individual patterns
                for pattern in compiled_patterns:
                    for match in pattern.finditer(block_text):
                        issue_number = None
                        
                        if len(match.groups()) == 1:
                            # Simple patterns like #123, GH-123, issue #123, bug #123
                            issue_number = int(match.group(1))
                        elif len(match.groups()) == 2:
                            # Full repo patterns like owner/repo#123 or full URLs
                            repo_name = match.group(1)
                            if repo_name.lower() == self.repo.full_name.lower():
                                issue_number = int(match.group(2))
                        
                        if issue_number is not None and issue_number > 0:
                            if is_issue(issue_number):
                                out.add(issue_number)
                
                # Check for PR references to skip them
                for pr_pattern in compiled_pr_patterns:
                    for match in pr_pattern.finditer(block_text):
                        logging.debug(f"Skipping PR reference: {match.group(0)}")
                            
        except Exception as e:
            logging.error(f"Error parsing commit message for issues: {e}")
            # Return what we found so far rather than failing completely
            return out

        return out

    def fixed_performance_issue(self) -> Optional[int]:
        msg = self.commit.commit.message or ""

        issue_refs = self.extract_fixed_issues()

        if not issue_refs:
            return None

        issue_title_body_tuples = []
        for number in issue_refs:
            try:
                gh_issue = self.repo.get_issue(number)

                if gh_issue.pull_request is not None:
                    continue

                title = gh_issue.title or ""
                body = gh_issue.body or ""

                issue_title_body_tuples.append((number, title, body))

                p = Prompt(messages=[Prompt.Message("user",
                    f"The following is an issue in the {self.repo.full_name} repository:\n\n###Issue Title###{title}\n###Issue Title End###\n\n###Issue Body###{body}\n###Issue Body End###"
                    + f"\n\nThe following is the commit message that fixes this issue:\n\n###Commit Message###{msg}\n###Commit Message End###"
                    + f"\n\nIs this issue likely to be related to improving execution time? Answer by only one word: 'yes' or 'no' (without any other text or punctuation). If you do not have enough information to decide, say 'no'."
                )])
                if self.config.llm["ollama"]:
                    self.llm = OllamaLLM(self.config.llm['ollama_stage1_model'])
                res = self.llm.generate(p)

                if "yes" in res.lower().strip():
                    logging.info(f"Commit {self.commit.sha} in {self.repo.full_name} is related to a likely performance issue prompted by GPT5_Nano (#{number}).")

                    # Also check with gpt5_codex
                    p = Prompt(messages=[Prompt.Message("user",
                        f"The following is an issue in the {self.repo.full_name} repository:\n\n###Issue Title###{title}\n###Issue Title End###\n\n###Issue Body###{body}\n###Issue Body End###"
                        + f"\n\nThe following is the commit message that fixes this issue:\n\n###Commit Message###{msg}\n###Commit Message End###"
                        + f"\n\nIs this issue related to improving execution time? Answer by only one word: 'yes' or 'no' (without any other text or punctuation). If you do not have enough information to decide, say 'no'.")], 
                    )
                    if self.config.llm["ollama"]:
                        self.llm = OllamaLLM(self.config.llm['ollama_stage2_model'])
                    res = self.llm.generate(p)

                    if "yes" in res.lower().strip():
                        logging.info(f"Commit {self.commit.sha} in {self.repo.full_name} is related to a likely performance issue prompted by GPT5_Codex (#{number}).")
                        return number

            except UnknownObjectException:
                continue
            
        logging.info(f"Commit {self.commit.sha} in {self.repo.full_name} is not fixing performance issues.")
        return None
