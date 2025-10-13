import json, logging, subprocess, re, threading
import src.config as conf
from typing import Any
from pathlib import Path
from src.filter.llm.prompt import Prompt
from src.filter.llm.openai import OpenRouterLLM

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
            subprocess.run(cmd, check=True)
            logging.info(f"Installed {dep_name} via {method}")
            return True
        except subprocess.CalledProcessError:
            logging.error(f"Failed to install {dep_name} via {method}")
            return False

    class PackageHandler:
        def get_missing_dependencies(self, stdout: str, stderr: str, cache_path: Path) -> set[str]:
            if not cache_path.exists():
                logging.warning("No CMakeCache.txt found, skipping")

            missing_cache = self._find_cache_missing(cache_path)
            logging.info(f"Missing caches: {missing_cache}")
            missing_pkgconfig = self._find_pkgconfig_missing(stdout, stderr)
            logging.info(f"Missing packages: {missing_pkgconfig}")

            '''
            missing_others: set[str] = set()
            for dep in missing_cache | missing_pkgconfig:
                if "-" in dep:
                    missing_others.add(dep.split("-")[0])
                if "+" in dep:
                    missing_others.add(dep.split("+")[0])
                if "_" in dep and len(dep.split("_")) > 1:
                    missing_others.add(dep.split("_")[0])
                if "_" in dep and len(dep.split("_")) > 2:
                    missing_others.add("_".join(dep.split("_")[0:2]))
                if "_" in dep and len(dep.split("_")) > 3:
                    missing_others.add("_".join(dep.split("_")[0:-1]))
            logging.info(f"Missing others: {missing_others}")
            '''

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
            ]
            missing = set()
            for pattern in patterns:
                missing.update(re.findall(pattern, stdout))
                missing.update(re.findall(pattern, stderr))
            return missing
        
    
    class LLMResolver:
        def __init__(self):
            self.llm = OpenRouterLLM(conf.llm['model'])

        def llm_prompt(self, deps: list[str], timeout: int = 60) -> str:
            result: dict[str, str] = {"out": ""}

            def run_llm():
                p = Prompt([Prompt.Message(
                    role="user",
                    content=f"""
                        You are an expert in CMake, Ubuntu, and vcpkg. 
                        Given a missing dependency name, return a JSON object like this:
                        {{
                        "<dependency>": {{
                            "apt": "<Ubuntu 22.04 package>",
                            "vcpkg": "<vcpkg port>",
                            "flags": {{
                                "apt": ["-D<VAR_INCLUDE_DIR>=<full_path_to_headers>", "-D<VAR_LIBRARY>=<full_path_to_library>"],
                                "vcpkg": ["-D<VAR_INCLUDE_DIR>=/opt/vcpkg/installed/x64-linux/include/<subdir_if_any>", "-D<VAR_LIBRARY>=/opt/vcpkg/installed/x64-linux/lib/<library_file>"]
                            }}
                        }}
                        }}
                        Rules:
                        1. Use the correct header subfolder if the package installs headers under a subdirectory (e.g., `/usr/include/leptonica`, `/usr/include/SDL2`, `/usr/include/freetype2`).
                        2. For vcpkg, mirror the subfolder inside `/opt/vcpkg/installed/x64-linux/include`.
                        3. Only return valid JSON, no explanations.
                        4. For invalid dependencies, set "<Ubuntu 22.04 package>" and "<vcpkg port>" to "".
                        5. Generate it for <dependency> if exists in [{deps}].
                        """
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
        

