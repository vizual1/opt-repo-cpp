import subprocess, logging, re, os, json
from pathlib import Path

CMAKE_TO_VCPKG = {
    'GTest': 'gtest',
    'GMock': 'gtest',
    'Boost': 'boost',
    'Qt5': 'qt5-base',
    'Qt5Core': 'qt5-base',
    'Qt5Widgets': 'qt5-base',
    'Qt6': 'qt6-base',
    'OpenCV': 'opencv',
    'Eigen3': 'eigen3',
    'Protobuf': 'protobuf',
    'gRPC': 'grpc',
    'ZLIB': 'zlib',
    'PNG': 'libpng',
    'CURL': 'curl',
    'OpenSSL': 'openssl',
    'SQLite3': 'sqlite3',
    'fmt': 'fmt',
    'spdlog': 'spdlog',
    'nlohmann_json': 'nlohmann-json',
    'Catch2': 'catch2',
    'doctest': 'doctest',
    'benchmark': 'benchmark',
    'gflags': 'gflags',
    'glog': 'glog',
    'yaml-cpp': 'yaml-cpp',
    'jsoncpp': 'jsoncpp',
    'RapidJSON': 'rapidjson',
    'Poco': 'poco',
    'cpprestsdk': 'cpprestsdk',
    'websocketpp': 'websocketpp',
    # System packages to ignore
    'Threads': None,
    'PkgConfig': None,
    'OpenMP': None,
    'MPI': None,
    'CUDA': None,
    'Python': None,
    'Python3': None,
}

class CMakeAutoBuilder:
    def __init__(self, root: str):
        self.flags: set[str] = set()
        self.root = root
        self.vcpkg_manifest_path = Path(self.root) / "vcpkg.json"
        self.vcpkg_root = Path("/opt/vcpkg/installed/x64-linux")

    def _normalize_dep_name(self, dep: str) -> str:
        """Normalize dependency names"""
        return dep.strip().lower().replace("-", "_").replace("::", "_")

    def inject_vcpkg_dependency(self, dep: str) -> bool:
        dep_norm = self._normalize_dep_name(dep)
        root = self.vcpkg_root
        inc_path = root / "include"
        lib_path = root / "lib"
        share_path = root / "share"
        debug_lib_path = root / "debug" / "lib"
        added = False

        include_candidates = [inc_path]  # always try the global include
        for sub in inc_path.glob(f"**/{dep_norm}*.h"):  # match headers
            if sub.parent.exists():
                include_candidates.append(sub.parent)

        # scan for include directory
        for path in include_candidates:
            if path.exists():
                self.flags.add(f"-D{dep.upper()}_INCLUDE_DIR={path}")
                self.flags.add(f"-D{dep.upper()}_INCLUDE_DIRS={path}")
                self.flags.add(f"-D{dep}_INCLUDE_DIR={path}")
                self.flags.add(f"-D{dep}_INCLUDE_DIRS={path}")
                logging.info(f"[vcpkg] Found include path for {dep}: {path}")
                added = True
                break

        # scan for library file
        lib_candidates = list(lib_path.glob(f"lib{dep_norm}*.a")) + list(lib_path.glob(f"lib{dep_norm}*.so"))
        if not lib_candidates:
            lib_candidates = list(debug_lib_path.glob(f"lib{dep_norm}*.a")) + list(debug_lib_path.glob(f"lib{dep_norm}*.so"))
        if lib_candidates:
            self.flags.add(f"-D{dep.upper()}_LIBRARY={lib_candidates[0]}")
            self.flags.add(f"-D{dep}_LIBRARY={lib_candidates[0]}")
            logging.info(f"[vcpkg] Found library for {dep}: {lib_candidates[0]}")
            added = True

        # check for modern CMake config file
        for cmake_dir in share_path.glob(f"{dep_norm}*"):
            config = next(cmake_dir.glob("*Config.cmake"), None)
            if config:
                self.flags.add(f"-D{dep.upper()}_DIR={config.parent}")
                self.flags.add(f"-D{dep}_DIR={config.parent}")
                logging.info(f"[vcpkg] Found CMake config for {dep}: {config}")
                added = True
                break

        # extend pkg-config search path
        pkgconfig_dir = lib_path / "pkgconfig"
        if pkgconfig_dir.exists():
            os.environ["PKG_CONFIG_PATH"] = f"{pkgconfig_dir}:{os.environ.get('PKG_CONFIG_PATH', '')}"
            logging.debug(f"[vcpkg] Added {pkgconfig_dir} to PKG_CONFIG_PATH")
        if not added:
            logging.warning(f"[vcpkg] Could not find any hints for dependency '{dep}'.")
        return added

    def generate_vcpkg_manifest(self, dependencies: set[str]) -> bool:
        """
        Parse CMakeLists.txt to extract find_package() calls and create vcpkg.json.
        """
        if not dependencies:
            logging.info("No find_package() calls found in CMakeLists.txt")
            return False
        
        vcpkg_deps = set()
        for dep in dependencies:
            vcpkg_name = self._map_to_vcpkg_name(dep)
            if vcpkg_name:
                vcpkg_deps.add(vcpkg_name)
        
        if not vcpkg_deps:
            logging.info("No vcpkg-installable dependencies found")
            return False
        
        logging.info(f"Detected dependencies: {vcpkg_deps}")
        
        manifest = {
            "name": Path(self.root).name.lower().replace("_", "-"),
            "version-string": "0.0.1",
            "dependencies": sorted(list(vcpkg_deps))
        }
        
        try:
            with open(self.vcpkg_manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            logging.info(f"Created vcpkg manifest at {self.vcpkg_manifest_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to write vcpkg manifest: {e}")
            return False
        
    def _map_to_vcpkg_name(self, cmake_name: str) -> str:
        """Map CMake package name to vcpkg package name."""
        if cmake_name in CMAKE_TO_VCPKG:
            return CMAKE_TO_VCPKG[cmake_name]
        
        vcpkg_name = cmake_name.lower()
        
        if re.match(r'[A-Z][a-z]+\d+', cmake_name):
            parts = re.findall(r'[A-Z][a-z]*\d*', cmake_name)
            vcpkg_name = '-'.join(p.lower() for p in parts)
        
        vcpkg_name = vcpkg_name.replace('_', '-')
        
        return vcpkg_name
        
    def add_to_manifest(self, new_deps: set[str]) -> bool:
        """Add new dependencies to existing vcpkg.json manifest."""
        if not self.vcpkg_manifest_path.exists():
            manifest = {
                "name": Path(self.root).name.lower().replace("_", "-"),
                "version-string": "0.0.1",
                "dependencies": []
            }
        else:
            try:
                with open(self.vcpkg_manifest_path, 'r') as f:
                    manifest = json.load(f)
            except Exception as e:
                logging.error(f"Failed to read existing manifest: {e}")
                return False
        
        current_deps = set(manifest.get("dependencies", []))
        for dep in new_deps:
            vcpkg_name = self._map_to_vcpkg_name(dep)
            if vcpkg_name:
                current_deps.add(vcpkg_name)
        
        manifest["dependencies"] = sorted(list(current_deps))
        
        try:
            with open(self.vcpkg_manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            logging.info(f"Updated manifest with {len(new_deps)} new dependencies")
            return True
        except Exception as e:
            logging.error(f"Failed to update manifest: {e}")
            return False