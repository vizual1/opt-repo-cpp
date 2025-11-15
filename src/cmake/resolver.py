import json, logging, subprocess, re, threading, jsonschema
import src.config as conf
from typing import Any
from pathlib import Path
from src.llm.prompt import Prompt
from src.llm.openai import OpenRouterLLM
from src.llm.ollama import OllamaLLM
from docker.models.containers import Container
from src.config.config import Config

LLM_DEP_SCHEMA = {
    "type": "object",
    "patternProperties": {
        "^.+$": {
            "type": "object",
            "properties": {
                "vcpkg": {"type": "string"},
                "apt": {"type": "string"},
                "flags": {
                    "type": "object",
                    "properties": {
                        "vcpkg": {"type": "array", "items": {"type": "string"}},
                        "apt": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["vcpkg", "apt"],
                    "additionalProperties": False,
                },
            },
            "required": ["vcpkg", "apt", "flags"],
            "additionalProperties": False,
        }
    },
    "additionalProperties": True,
}

class DependencyResolver:
    
    class DependencyCache:
        def __init__(self, config: Config):
            self.mapping_path = Path(config.storage_paths.get("cmake-dep", "cmake-dep.json"))
            try:
                with open(self.mapping_path) as f:
                    self.mapping: dict[str, dict[str, Any]] = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logging.warning(f"Initializing empty cache ({e})")
                self.mapping = {}

        def save(self):
            def reset_permissions(path: Path):
                """Reset file permissions to writable"""
                try:
                    if path.exists():
                        path.chmod(0o666)  # Read/write for all
                except Exception:
                    pass
            
            tmp_path = self.mapping_path.with_suffix(".tmp")

            reset_permissions(self.mapping_path)
            reset_permissions(tmp_path)
            
            try:
                with open(tmp_path, "w") as f:
                    json.dump(self.mapping, f, indent=4)
                
                if self.mapping_path.exists():
                    self.mapping_path.unlink()
                tmp_path.replace(self.mapping_path)
                
            except PermissionError as e:
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except PermissionError:
                    pass
                logging.error(f"Failed to save cache: {e}")
                raise
        
    def __init__(self, config: Config, cache=None, handler=None, llm=None):
        self.config = config
        self.cache = cache or self.DependencyCache(self.config)
        self.package_handler = handler or self.PackageHandler()
        self.llm = llm or self.LLMResolver(self.config)

    def resolve_all(self, dep_names: set[str], container: Container) -> tuple[set[str], set[str]]:
        self.container = container
        unresolved: set[str] = set() 
        flags: set[str] = set()

        for dep in map(str.lower, dep_names):
            info = self.resolve(dep)
            if not info:
                logging.warning(f"Unresolved dependency {dep}")
                unresolved.add(dep)
                continue

            for method in ("apt", "vcpkg"):
                if self.install(dep, method):
                    flags |= self.flags(dep, method)
                    break
                else:
                    self.cache.mapping.setdefault(dep, {method: ""})

            self.cache.save()

        return unresolved, flags
        
    def resolve(self, dep_name: str) -> dict[str, Any]:
        if dep_name in self.cache.mapping:
            return self.cache.mapping[dep_name]
        else:
            return {}
    
    def flags(self, dep_name: str, method: str) -> set[str]:
        dep = self.cache.mapping.get(dep_name)
        if not dep:
            return set()

        flags = dep.get("flags", {})
        if method not in flags:
            return set()

        return set(flags[method])
        
    def install(self, dep_name: str, method: str) -> bool:
        info = self.resolve(dep_name)
        pkg_name = info.get(method)
        if not pkg_name:
            logging.warning(f"{method} mapping for {dep_name} is missing or empty.")
            return False

        cmd = {
            "vcpkg": ["/opt/vcpkg/vcpkg", "install", pkg_name],
            "apt": ["apt-get", "install", "-y", pkg_name]
        }[method]

        logging.info(f"Installing {dep_name} via {method}...")
        try:
            if self.container:
                exit_code, output = self.container.exec_run(cmd)
                logging.debug(output.decode(errors="ignore") if output else "")
                return exit_code == 0
            else:
                subprocess.run(cmd, check=True)
            logging.info(f"Installed {dep_name} via {method}")
            return True
        except subprocess.CalledProcessError:
            logging.error(f"Failed to install {dep_name} via {method}")
        except FileNotFoundError:
            logging.error(f"{method} executable not found on system.")
        return False
        
    def unresolved_dep(self, unresolved_dependencies: set[str]) -> tuple[set[str], set[str]]:
        logging.info(f"All unresolved dependencies {unresolved_dependencies}")
        llm_output = self.llm.llm_prompt(list(unresolved_dependencies), timeout=100)
        logging.info(f"LLM prompt returned:\n{llm_output}")

        if not llm_output.strip():
            logging.error("LLM returned empty output.")
            return unresolved_dependencies, set()
        
        try:
            data = json.loads(llm_output)
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON from LLM output: {e}")
            return unresolved_dependencies, set()
        
        try:
            jsonschema.validate(instance=data, schema=LLM_DEP_SCHEMA)
        except jsonschema.ValidationError as e:
            logging.error(f"LLM output failed schema validation: {e.message}")
            logging.debug(f"Invalid data: {json.dumps(data, indent=2)}")
            return unresolved_dependencies, set()

        data = {k.lower() if isinstance(k, str) else k: v for k, v in data.items()}
        self.cache.mapping.update(data)
        unresolved_dependencies, other_flags = self.resolve_all(unresolved_dependencies, self.container)
        self.cache.save()
        
        logging.info(f"Added {data.keys()} to dependency cache")
        return unresolved_dependencies, other_flags
    

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
            if not cache_path.exists():
                logging.warning(f"No CMakeCache.txt at {cache_path}")
                return set()
            
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
        def __init__(self, config: Config):
            self.config = config 
            if self.config.llm.ollama_enabled:
                self.llm = OllamaLLM(self.config, self.config.llm.ollama_resolver_model)
            else:
                self.llm = OpenRouterLLM(self.config, self.config.llm.ollama_resolver_model)

        def llm_prompt(self, deps: list[str], timeout: int = 60) -> str:
            result: dict[str, str] = {"out": ""}

            def run_llm():
                p = Prompt([Prompt.Message(
                    "user",
                    self.config.resolver_prompt.replace("<deps>", f"{deps}")
                )])
                try:
                    llm_output = self.llm.generate(p)
                    result["out"] = self._clean_json_output(llm_output)
                except Exception as e:
                    logging.warning(f"LLM call failed {e}")

            t = threading.Thread(target=run_llm, daemon=True)
            t.start()
            t.join(timeout)

            if t.is_alive():
                logging.warning(f"LLM query timed out after {timeout} seconds.")

            return result["out"]
        
        def _clean_json_output(self, raw_text: str) -> str:
            """Extract JSON content from LLM output."""
            match = re.search(r"```json\s*(\{.*\})\s*```", raw_text, re.DOTALL) or re.search(r"(\{.*\})", raw_text, re.DOTALL)
            if not match:
                logging.warning("No JSON block found in LLM output.")
                return "{}"
            return match.group(1).strip()
        

