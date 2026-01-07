import re, logging, os, json
from github.Commit import Commit
from github.Repository import Repository
from src.llm.prompt import Prompt
from src.llm.openai import OpenRouterLLM
from src.llm.ollama import OllamaLLM
from typing import Optional
from src.config.config import Config
from github.GithubException import UnknownObjectException


class CommitFilter:
    def __init__(self, commit: Commit, config: Config, repo: Repository):
        self.commit = commit
        self.config = config
        self.llm1 = OpenRouterLLM(self.config, self.config.llm.model1)
        self.llm2 = OpenRouterLLM(self.config, self.config.llm.model2)
        self.repo = repo
        self.cache: dict[str, dict[str, dict[str, bool]]] = self._load_cache()

    def accept(self) -> bool: 
        logging.info(f"[{self.repo.full_name}] ({self.commit.sha}) Filtering...")
        name = self.config.llm.ollama_stage1_model + "_" + self.config.llm.ollama_diff_model + "_" + self.config.llm.ollama_stage2_model if self.config.llm.ollama_enabled else self.config.llm.model1 + "_" + self.config.llm.model2
        cached = self.cache.get(self.repo.full_name, {}).get(self.config.filter_type + (f"_{name}" if self.config.filter_type == "llm" else ""), {}).get(self.commit.sha)
        if cached is not None:
            logging.info(f"Cache hit for {self.commit.sha} ({self.config.filter_type}) -> {cached}")
            return cached

        if self.config.filter_type == "simple":
            result = self._simple_filter() and self.only_cpp_source_modified()
            self._save_cache(self.commit, result)
        elif self.config.filter_type == "llm":
            result = self.only_cpp_source_modified() and self._llm_filter() 
            self._save_cache(self.commit, result, extra=f"_{name}")
        elif self.config.filter_type == "issue":
            result = self.only_cpp_source_modified() and self._fixed_performance_issue() is not None
            self._save_cache(self.commit, result, extra=f"_{name}")
        else:
            result = False

        return result
    
############ LLM ############
    
    def _llm_filter(self) -> bool:
        """Uses the issue/PR filter + commit message filter + diff filter"""
        performance_issue = self._fixed_performance_issue()
        if performance_issue:
            return True

        msg = self.commit.commit.message

        # ============ STAGE 1: Commit Message Analysis ============
        system_prompt = (
            "You are a strict binary classifier. "
            "Determine if the commit improves runtime performance (makes code execute faster). "
            "Do not count bug fixes, correctness changes, refactoring, or style cleanups. "
            "Respond ONLY in JSON: {\"answer\": \"yes\"}, {\"answer\": \"no\"}, or {\"answer\": \"maybe\"}."
        )

        user_prompt = (
            f"Repository: {self.repo.full_name}\n"
            f"Commit Message:\n{msg}\n\n"
            f"Question: Does this commit message indicate a runtime performance improvement?"
        )

        p = Prompt([
            Prompt.Message("system", system_prompt),
            Prompt.Message("user", user_prompt)
        ])

        if self.config.llm.ollama_enabled:
            self.llm = OllamaLLM(self.config, self.config.llm.ollama_stage1_model)
        logging.info(f"[{self.repo.full_name}] First LLM prompt: {p.messages[1].content}")
        res = self.llm.generate(p)
        logging.info(f"[{self.repo.full_name}] First LLM returned: {res}")

        res_lower = res.lower()
        stage1_answer = "maybe"
        if "yes" in res_lower and "no" not in res_lower:
            stage1_answer = "yes"
        elif "no" in res_lower:
            stage1_answer = "no"

        if stage1_answer == "no":
            logging.info(f"[{self.repo.full_name}] Stage 1 rejected (no)")
            return False

        diff_text = None

        # ============ STAGE 1.5: Diff Verification ============
        if stage1_answer == "maybe":
            logging.info(f"[{self.repo.full_name}] Stage 1 uncertain, checking file diffs...")
            
            any_file_performance = False
            files_checked = 0
            
            for f in self.commit.files:
                if not f.patch:
                    continue
                    
                files_checked += 1
                
                patch = f.patch
                if len(patch) > 8000:
                    patch = patch[:8000] + "\n... [diff truncated] ..."
                
                diff_text = f"File: {f.filename}\n{patch}"

                system_prompt = (
                    "You are a strict binary classifier. "
                    "Determine if the commit improves runtime performance (makes code execute faster). "
                    "Do not count bug fixes, correctness changes, refactoring, or style cleanups. "
                    "Respond ONLY in JSON: {\"answer\": \"yes\"} or {\"answer\": \"no\"}. "
                    "If you do not have enough information to decide, say {\"answer\": \"no\"}. "
                )
                
                file_prompt = (
                    f"Repository: {self.repo.full_name}\n"
                    f"Commit Message:\n{msg}\n\n"
                    f"One of the patched files (diff):\n{diff_text}\n\n"
                    f"Question: Does this diff show a test measureable runtime performance improvement?"
                )
                
                p = Prompt([
                    Prompt.Message("system", system_prompt),
                    Prompt.Message("user", file_prompt)
                ])
                
                if self.config.llm.ollama_enabled:
                    self.llm = OllamaLLM(self.config, self.config.llm.ollama_diff_model)
                
                logging.info(f"[{self.repo.full_name}] Checking file {f.filename}:\n{p.messages[1].content}")
                res = self.llm.generate(p)
                logging.info(f"[{self.repo.full_name}] File {f.filename} response: {res}")
                
                if "yes" in res.lower() and "no" not in res.lower():
                    any_file_performance = True
                    logging.info(f"[{self.repo.full_name}] File {f.filename} indicates performance improvement")
                    return True
            
            if not any_file_performance:
                logging.info(f"[{self.repo.full_name}] No files indicate performance improvement ({files_checked} checked)")
                return False
        
        # ============ STAGE 2: Full Context Verification ============        
        logging.info(f"[{self.repo.full_name}] Proceeding to Stage 2 verification")

        diff_text = self.get_diff()
        
        stage2_system = (
            "You are a strict binary classifier. "
            "Determine if the commit improves runtime performance (makes code execute faster). "
            "Do not count bug fixes, correctness changes, refactoring, or style cleanups. "
            "Respond ONLY in JSON: {\"answer\": \"yes\"} or {\"answer\": \"no\"}."
            "If you do not have enough information to decide, say {\"answer\": \"no\"}."
        )
            
        stage2_prompt = (
            f"Repository: {self.repo.full_name}\n"
            f"Commit Message:\n{msg}\n\n"
            f"Code Changes:\n{diff_text}\n\n"
            f"Question: Does this commit improve test measurable runtime performance?"
        )
        
        p = Prompt([
            Prompt.Message("system", stage2_system),
            Prompt.Message("user", stage2_prompt)
        ])
        
        if self.config.llm.ollama_enabled:
            self.llm = OllamaLLM(self.config, self.config.llm.ollama_stage2_model)
        logging.info(f"[{self.repo.full_name}] Second LLM prompt: {p.messages[1].content}")
        res = self.llm.generate(p)
        logging.info(f"[{self.repo.full_name}] Second LLM returned: {res}")
        if 'yes' in res.lower() and "no" not in res.lower():
            return True
            
        return False
    
    def get_diff(self) -> str:
        diff_lines: list[str] = []
        for f in self.commit.files:
            if f.patch:
                diff_lines.append(f"--- {f.filename}")
                patch = f.patch
                if len(patch) > 8000:
                    diff_lines.append("\n... [diff truncated] ...")
                    break
                diff_lines.append(patch[:8000])
        return "\n".join(diff_lines)

    def _modify_cpp_filter(self) -> bool:
        """Returns True if the commit modifies any C++ source or header files."""
        cpp_extensions = (".cpp", ".cc", ".cxx", ".c++", ".h", ".hpp")
        ignore_dirs = ("third_party", "vendor", "external")
        for f in self.commit.files:
            if f.filename.endswith(cpp_extensions) and not any(d in f.filename for d in ignore_dirs):
                return True
        return False
    
    def only_cpp_source_modified(self) -> bool:
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
            
            if any(tdir in filename for tdir in self.config.valid_test_dirs):
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

############ ISSUE ############

    def _fixed_performance_issue(self) -> Optional[int]:
        """Returns the first performance issue found. Prompts LLM to check."""
        performance_issues = self.get_all_performance_issues()
        return min(performance_issues) if performance_issues else None

    def _is_performance_issue(self, number: int, ref_type: str) -> bool:
        """
        Check if an issue/PR is related to performance using LLM.
        
        Args:
            number: Issue or PR number
            ref_type: "issue" or "pull_request"
            
        Returns:
            True if it's a performance-related issue
        """
        try:
            gh_issue = self.repo.get_issue(number)
            title = gh_issue.title or ""
            body = gh_issue.body or ""
            msg = self.commit.commit.message or ""
            ref_type_display = ref_type.replace('_', ' ')

            system = (
                "You are a strict binary classifier. "
                "Determine if the commit improves runtime performance (e.g., reduces CPU usage, improves memory efficiency, speeds up execution). "
                "Do not count bug fixes, correctness changes, refactoring, or style cleanups as performance improvements. "
                "Respond ONLY in this JSON format: {\"answer\": \"yes\"} or {\"answer\": \"no\"}. "
                "If you do not have enough information to decide, say {\"answer\": \"no\"}."
                "Do not add any explanation or commentary."
            )
                
            user = (
                f"The following is a {ref_type_display} in the {self.repo.full_name} repository:\n\n"
                f"###{ref_type_display} Title###{title}\n###{ref_type_display} Title End###\n\n"
                f"###{ref_type_display} Body###{body}\n###{ref_type_display} Body End###\n\n"
                f"The following is the commit message that fixes this {ref_type_display}:\n\n"
                f"###Commit Message###{msg}\n###Commit Message End###\n\n"
                f"Answer strictly in this JSON format (do not add any explanation):\n"
                f"{{\"answer\": \"yes\"}} or {{\"answer\": \"no\"}}.\n\n"
                f"Question: Is this issue likely related to improving execution time?"
            )

            p = Prompt([
                Prompt.Message("system", system),
                Prompt.Message("user", user)
            ])
        
            
            # First LLM check
            if self.config.llm.ollama_enabled:
                self.llm1 = OllamaLLM(self.config, self.config.llm.ollama_stage1_model)
            
            logging.info(f"First LLM check for #{number}")
            res = self.llm1.generate(p)
            logging.info(f"First LLM response: {res}")
            
            if "yes" not in res.lower().strip():
                return False
            
            # Second LLM check for confirmation
            if self.config.llm.ollama_enabled:
                self.llm2 = OllamaLLM(self.config, self.config.llm.ollama_stage2_model)
            
            logging.info(f"Second LLM check for #{number}")
            res = self.llm2.generate(p)
            logging.info(f"Second LLM response: {res}")
            
            return "yes" in res.lower().strip()
            
        except UnknownObjectException:
            logging.warning(f"Issue/PR #{number} not found")
            return False
        except Exception as e:
            logging.error(f"Error checking if #{number} is performance issue: {e}")
            return False

    def extract_fixed_issues(self) -> dict[int, str]:
        """Extract issue/PR numbers from commit message that are explicitly closed/fixed."""
        commit_message = self.commit.commit.message
        if not commit_message:
            return {}
            
        msg = commit_message.strip()
        results: dict[int, str] = {}

        closing_prefix = r'(?:(?<![A-Za-z])(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved|address|addresses|addressed))(?:\s*[:\-])?\s+'
        issue_patterns = [r'#(\d+)', r'GH-(\d+)', r'issue\s*#(\d+)', r'bug\s*#(\d+)']
        full_repo_patterns = [r'([\w.-]+/[\w.-]+)#(\d+)', r'https?://github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)']
        pr_patterns = [r'https?://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)']
        
        all_issue_patterns = issue_patterns + full_repo_patterns
        compiled_issue_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in all_issue_patterns]
        compiled_pr_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in pr_patterns]
        
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

                for pr_pattern in compiled_pr_patterns:
                    for match in pr_pattern.finditer(block_text):
                        repo_name = match.group(1)
                        number = int(match.group(2))
                        if repo_name.lower() == self.repo.full_name.lower():
                            results[number] = "pull_request"
                            logging.info(f"Found PR reference: {repo_name}#{number}")

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

    def get_issues_from_pr(self, pr_number: int) -> set[int]:
        """
        Get all issues that a PR fixes/closes using GitHub's API.
        
        Args:
            pr_number: The pull request number
            
        Returns:
            Set of issue numbers that the PR closes
        """
        try:
            pr = self.repo.get_pull(pr_number)
            closed_issues = set()
            if pr.body:
                closing_pattern = re.compile(
                    r'(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)s?\s+#(\d+)',
                    re.IGNORECASE
                )
                for match in closing_pattern.finditer(pr.body):
                    closed_issues.add(int(match.group(1)))
            
            # Use GitHub's timeline API to get linked issues
            # This captures issues linked via the UI
            try:
                events = pr.get_issue_events()
                for event in events:
                    if event.event == "connected" and event.issue:
                        closed_issues.add(event.issue.number)
            except Exception as e:
                logging.warning(f"Could not fetch events for PR #{pr_number}: {e}")
            
            logging.info(f"PR #{pr_number} closes issues: {closed_issues}")
            return closed_issues
            
        except UnknownObjectException:
            logging.warning(f"PR #{pr_number} not found in {self.repo.full_name}")
            return set()
        except Exception as e:
            logging.error(f"Error fetching issues from PR #{pr_number}: {e}")
            return set()


    def get_all_performance_issues(self) -> set[int]:
        """
        Get all unique performance issues fixed by this commit.
        Handles both direct issue references and issues closed by referenced PRs.
        
        Returns:
            Set of unique performance issue numbers
        """
        refs = self.extract_fixed_issues()
        if not refs:
            return set()
        
        performance_issues = set()
        issues_to_check: list[tuple[int, str]] = []
        
        for number, ref_type in refs.items():
            if ref_type == "pull_request":
                pr_issues = self.get_issues_from_pr(number)
                for issue_num in pr_issues:
                    issues_to_check.append((issue_num, "issue"))
                issues_to_check.append((number, ref_type))
            else:
                issues_to_check.append((number, ref_type))
        
        checked = set()
        for number, ref_type in issues_to_check:
            if number in checked:
                continue
            checked.add(number)
            
            if self._is_performance_issue(number, ref_type):
                performance_issues.add(number)
                logging.info(f"Identified performance issue: #{number}")
        
        if performance_issues:
            logging.info(
                f"Commit {self.commit.sha} fixes {len(performance_issues)} "
                f"unique performance issue(s): {sorted(performance_issues)}"
            )
        else:
            logging.info(f"Commit {self.commit.sha} does not fix any performance issues")
        
        return performance_issues
    
############ SIMPLE ############

    def _simple_filter(self) -> bool:
        """Simple filter only checks if there are keywords used in the commit message"""
        msg = self.commit.commit.message.lower()
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
        return any(k in msg for k in perf_label_keywords | perf_text_keywords | runtime_hint_keywords)
