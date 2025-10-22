import json, logging, subprocess, re, threading
import src.config as conf
from typing import Any
from pathlib import Path
from src.filter.llm.prompt import Prompt
from src.filter.llm.openai import OpenRouterLLM
from src.filter.llm.ollama import OllamaLLM
from docker.models.containers import Container

class DependencyResolver:

    class DependencyCache:
        def __init__(self):
            self.mapping_path = conf.storage["cmake-dep"]
            with open(self.mapping_path) as f:
                self.mapping: dict[str, dict[str, Any]] = json.load(f)

        def save(self):
            with open(self.mapping_path, "w") as f:
                json.dump(self.mapping, f, indent=4)
    
    def __init__(self):
        self.cache = self.DependencyCache()
        self.package_handler = self.PackageHandler()
        self.llm = self.LLMResolver()

    def resolve_all(self, dep_names: set[str], container: Container) -> tuple[set[str], set[str]]:
        self.container = container
        unresolved_dependencies: set[str] = set() 
        other_flags: set[str] = set()
        for dep in dep_names:
            resolve = self.resolve(dep.lower())
            if not resolve:
                unresolved_dependencies.add(dep)
                logging.warning(f"Unresolved dependency {dep}")
                continue
            
            dep = dep.lower()
            if self.install(dep, method="apt"):
                other_flags |= self.flags(dep, method="apt")
            elif self.install(dep, method="vcpkg"):
                self.cache.mapping[dep]["apt"] = ""
                other_flags |= self.flags(dep, method="vcpkg")
            else:
                self.cache.mapping[dep]["apt"] = ""
                self.cache.mapping[dep]["vcpkg"] = ""
            self.cache.save()
        return unresolved_dependencies, other_flags
        
    def resolve(self, dep_name: str) -> dict[str, Any]:
        if dep_name in self.cache.mapping:
            return self.cache.mapping[dep_name]
        else:
            return {}
    
    def flags(self, dep_name: str, method: str) -> set[str]:
        return set(self.cache.mapping[dep_name]["flags"][method])
    
    def install(self, dep_name: str, method: str) -> bool:
        info = self.resolve(dep_name)
        if not info:
            logging.warning(f"Unknown dependency: {dep_name}")
            return False
        assert method == "apt" or method == "vcpkg"
        pkg_name = info.get(method)
        if not pkg_name:
            logging.warning(f"{method} mapping for {dep_name} is empty")

        cmd = {
            "vcpkg": ["/opt/vcpkg/vcpkg", "install", pkg_name],
            "apt": ["apt-get", "install", "-y", pkg_name]
        }[method]

        try:
            logging.info(f"Installing {dep_name} via {method}...")
            if self.container:
                exit_code, output = self.container.exec_run(cmd)
                #output = output.decode() if output else ""
                return exit_code == 0
            else:
                subprocess.run(cmd, check=True)
            logging.info(f"Installed {dep_name} via {method}")
            return True
        except subprocess.CalledProcessError:
            logging.error(f"Failed to install {dep_name} via {method}")
            return False
        
    def unresolved_dep(self, unresolved_dependencies: set[str]) -> tuple[set[str], set[str]]:
        logging.info(f"All unresolved dependencies {unresolved_dependencies}")
        llm_output = self.llm.llm_prompt(list(unresolved_dependencies), timeout=100)
        logging.info(f"LLM prompt returned:\n{llm_output}")
        try:
            data: dict[str, dict[str, Any]] = json.loads(llm_output)
            data = {k.lower() if isinstance(k, str) else k: v for k, v in data.items()}
            self.cache.mapping.update(data)
            unresolved_dependencies, other_flags = self.resolve_all(unresolved_dependencies, self.container)
            logging.info(f"Added {data.keys()} to dependency cache")
            return unresolved_dependencies, other_flags
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON for {llm_output}: {e}")
            return set(), set()

    class PackageHandler:
        def get_missing_dependencies(self, stdout: str, stderr: str, cache_path: Path) -> set[str]:
            if not cache_path.exists():
                logging.warning("No CMakeCache.txt found, skipping")
            
            missing_cache = self._find_cache_missing(cache_path)
            logging.info(f"Missing caches: {missing_cache}")
            missing_pkgconfig = self._find_pkgconfig_missing(stdout, stderr)
            logging.info(f"Missing packages: {missing_pkgconfig}")

            return missing_cache | missing_pkgconfig

        def _find_cache_missing(self, cache_path: Path) -> set[str]:
            missing = set()
            with open(cache_path) as f:
                for line in f:
                    if m := re.match(r"(\w+_DIR):PATH=(.+-NOTFOUND)", line):
                        missing.add(m.group(1).replace("_DIR", ""))
                    elif m := re.match(r"(\w+_FOUND):BOOL=FALSE", line):
                        missing.add(m.group(1).replace("_FOUND", ""))
            return missing
        
        def _find_pkgconfig_missing(self, stdout: str, stderr: str) -> set[str]:
            patterns = [
                r"No package '([a-zA-Z0-9_\-\+\.]+)' found",
                r"Could NOT find ([A-Za-z0-9_\-\+\.]+)",
                r"Could not find a package configuration file provided by \"([^\"]+)\"",
                r"Could not find a configuration file for package \"([^\"]+)\"",
                r"([A-Za-z0-9_\-\+\.]+)\s+package NOT found",
                r"No module named ['\"]([^'\"]+)['\"]",
                r"executable '([a-zA-Z0-9_\-\+\.]+)' not found",
            ]
            missing = set()
            for pattern in patterns:
                missing.update(re.findall(pattern, stdout))
                missing.update(re.findall(pattern, stderr))
            return missing
        
    
    class LLMResolver:
        def __init__(self):
            if conf.llm["ollama"]:
                self.llm = OllamaLLM(conf.llm['ollama_model'])
            else:
                self.llm = OpenRouterLLM(conf.llm['model'])

        def llm_prompt(self, deps: list[str], timeout: int = 60) -> str:
            result: dict[str, str] = {"out": ""}

            def run_llm():
                p = Prompt([Prompt.Message(
                    "user",
                    conf.resolver['resolver_message'].replace("<deps>", f"{deps}")
                )])
                try:
                    llm_output = self.llm.generate(p)
                    result["out"] = self._clean_json_output(llm_output)
                except Exception as e:
                    logging.warning(f"LLM call failed {e}")
                    result["out"] = ""

            t = threading.Thread(target=run_llm, daemon=True)
            t.start()
            t.join(timeout)

            if t.is_alive():
                logging.warning(f"LLM query timed out after {timeout} seconds.")
                return ""

            return result["out"]
        
        def _clean_json_output(self, raw_text: str) -> str:
            """Extract JSON content from LLM output."""
            match = re.search(r"```json\s*(\{.*\})\s*```", raw_text, re.DOTALL)
            if not match:
                match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
            if not match:
                raise ValueError("No valid JSON found in response.")
            return match.group(1).strip()
        

