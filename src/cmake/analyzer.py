import re
from pathlib import Path
from typing import List, Tuple, Dict
from src.cmake.parser import Parser

import logging
from src.cmake.parser import CMakeParser
from src.utils.package_resolver import find_apt_package

class CMakeAnalyzer:
    """
    High-level interface for analyzing CMake repositories.
    """
    def __init__(self, root: str):
        self.root = root
        self.parser = CMakeParser(self.root)
        self.cmakelists = self.parser.find_files(search="CMakeLists.txt")
        logging.info(f"CMakeLists.txt: {self.cmakelists}")

    def is_cmake_root(self) -> bool:
        return self.parser.is_cmake_root()

    def has_testing(self) -> bool:
        return (self.parser.check_add_test_defined(self.cmakelists) and 
                self.parser.check_enable_testing_defined(self.cmakelists))
    #TODO: self.parser.check_add_test_defined(self.cmakelists) or add_cpp_test?

    def has_build_testing_flag(self) -> bool:
        return self.parser.check_build_testing_flag(self.cmakelists)

    def has_ctest(self) -> bool:
        return self.parser.check_ctest_defined(self.cmakelists)
    
    def has_enable_testing(self) -> bool:
        return self.parser.check_enable_testing_defined(self.cmakelists)
    
    def get_testfile(self) -> list[str]:
        return self.parser.find_files(search="CTestTestfile.cmake")
    
    def get_ctest_flags(self) -> set[str]:
        return self.parser.parse_ctest_flags(self.cmakelists)

    def get_enable_testing_flags(self) -> set[str]:
        return self.parser.find_testing_flags(self.root)

    def get_dependencies(self) -> set[str]:
        deps = set()
        for cf in self.cmakelists:
            deps |= self.parser.get_cmake_packages(cf)
        return deps


class CMakeFlagsAnalyzer:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

        self.enable_testing_pattern = re.compile(r'enable_testing\s*\(', re.IGNORECASE)
        self.add_test_pattern = re.compile(r'add_test\s*\(', re.IGNORECASE)
        self.add_subdir_pattern = re.compile(r'add_subdirectory\s*\(\s*([^\s\)]+)')
        self.if_pattern = re.compile(r'^\s*if\s*\(\s*(.+?)\s*\)', re.IGNORECASE)
        self.elseif_pattern = re.compile(r'^\s*elseif\s*\(\s*(.+?)\s*\)', re.IGNORECASE)
        self.else_pattern = re.compile(r'^\s*else', re.IGNORECASE)
        self.endif_pattern = re.compile(r'^\s*endif', re.IGNORECASE)


    def _find_targets(self) -> Tuple[List[Tuple[Path, int]], List[Tuple[Path, int]]]:
        """
        Finds all enable_testing() and add_test() in CMakeLists.txt.
        Saves as a tuple of Path to CMakeLists.txt and line number.
        """
        enable_testing_files = []
        add_test_files = []

        for cmake_file in self.root.rglob("CMakeLists.txt"):
            with open(cmake_file, 'r', errors='ignore') as f:
                for i, line in enumerate(f):
                    if self.enable_testing_pattern.search(line):
                        enable_testing_files.append((cmake_file, i + 1))
                    if self.add_test_pattern.search(line):
                        add_test_files.append((cmake_file, i + 1))

        return enable_testing_files, add_test_files


    def _find_add_subdirectory_guard(self, root_file: Path, sub_file: Path) -> List[Tuple[Path, List[str]]]:
        """
        Find the flags needed to reach add_subdirectory (directory with CMakeLists.txt with enable_testing() or add_test())
        """
        guards = []
        stack: list[str] = []

        with open(root_file, 'r', errors='ignore') as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue

                if self.if_pattern.match(stripped):
                    stack.append("IF")
                    cond = Parser().parse_parenthesis(stripped)
                    stack.append(cond)
                elif self.elseif_pattern.match(stripped):
                    cond = Parser().parse_parenthesis(stripped)
                    stack.append(cond)
                elif self.else_pattern.match(stripped):
                    stack.append("ELSE")
                elif self.endif_pattern.match(stripped):
                    while stack:
                        out = stack.pop()
                        if out == "IF":
                            break

                if m := self.add_subdir_pattern.search(stripped):
                    subdir = m.group(1)
                    target_path = (root_file.parent / subdir / "CMakeLists.txt").resolve()
                    if target_path == sub_file.resolve():
                        conditions = []
                        op = 1
                        until_if = False
                        for c in stack[::-1]:
                            if c == "ELSE":
                                op = 0
                                until_if = True
                            elif c == "IF":
                                op = 1
                                until_if = False 
                            else:
                                conditions.append(f"{op}({c})")
                                if not until_if:
                                    op = 0
                        guards.append((root_file, conditions)) 

        return guards


    def _collect_all_guards(self, target_file: Path) -> List[Tuple[Path, List[str]]]:
        """
        Collects all flags of nested add_subdirectory until directory 
        with CMakeLists.txt with enable_testing() or add_test().
        """
        guards_chain = []
        save_cmake = ""
        current_file = target_file

        parent_dir = current_file.parent.parent
        parent_cmake = parent_dir / "CMakeLists.txt"

        if parent_cmake == current_file: # already at root
            return guards_chain 

        while True:
            if save_cmake == parent_cmake: # no change: already at root
                break

            if parent_cmake.exists():
                guards = self._find_add_subdirectory_guard(parent_cmake, current_file)
                if guards:
                    guard_file, conditions = guards[0]
                    test = self._collect_all_guards(guard_file)
                    if test:
                        for t in test:
                            p, c = t
                            c += conditions
                            guards_chain.append((p, c))
                    else:
                        guards_chain.append((guard_file, conditions))
                    current_file = guard_file
                else:
                    break
            else:
                save_cmake = parent_cmake
                parent_dir = parent_dir.parent
                parent_cmake = parent_dir / "CMakeLists.txt"
        print(guards_chain)
        return guards_chain[::-1]  # reverse to go root to target
    

    def _parse_conditional_targets(self, cmake_file: Path, pattern: re.Pattern) -> List[List[str]]:
        """
        Parse a single CMake file for all pattern (add_test or enable_testing),
        capturing the full conditional stack for each occurrence.
        """
        targets = []
        stack = []
        lines = cmake_file.read_text(errors="ignore").splitlines()

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if self.if_pattern.match(stripped):
                stack.append("IF")
                cond = Parser().parse_parenthesis(stripped)
                stack.append(cond)
            elif self.elseif_pattern.match(stripped):
                cond = Parser().parse_parenthesis(stripped)
                stack.append(cond) 
            elif self.else_pattern.match(stripped):
                stack.append("ELSE")
            elif self.endif_pattern.match(stripped):
                while stack:
                    out = stack.pop()
                    if out == "IF":
                        break
            if pattern.search(stripped):
                conditions = []
                op = 1
                until_if = False
                for c in stack[::-1]:
                    if c == "ELSE":
                        op = 0
                        until_if = True
                    elif c == "IF":
                        op = 1
                        until_if = False 
                    else:
                        conditions.append(f"{op}({c})")
                        if not until_if:
                            op = 0
                targets.append(conditions) #self.capture_conditions(stack.copy()))

        return targets


    def _analyze_target_file(self, cmake_file: Path, pattern: re.Pattern) -> List[List[str]]:
        """
        Combine recursive add_subdirectory guards and local conditional stacks
        for every occurrence of the pattern.
        """
        all_targets = []

        # Collect add_subdirectory guards up to root
        guards_chain = self._collect_all_guards(cmake_file)
        local_targets = self._parse_conditional_targets(cmake_file, pattern)

        for local_stack in local_targets:
            combined_stack = []
            for guard_file, guard_stack in guards_chain:
                combined_stack.extend(guard_stack)
            combined_stack.extend(local_stack)
            all_targets.append(combined_stack)

        return all_targets


    def analyze(self) -> Dict[str, Dict[str, List[List[str]]]]:
        enable_testing_targets, add_test_targets = self._find_targets()

        results = {"enable_testing_flags": {}, "add_test_flags": {}}

        for file, _ in enable_testing_targets:
            stacks = self._analyze_target_file(file, self.enable_testing_pattern)
            results["enable_testing_flags"][str(file)] = stacks

        for file, _ in add_test_targets:
            stacks = self._analyze_target_file(file, self.add_test_pattern)
            results["add_test_flags"][str(file)] = stacks

        return results


