import re
from pathlib import Path
from typing import Union
from collections import defaultdict

def parse_framework_output(output: str, framework: str, test_name: str) -> float:
    if framework == "gtest":
        pattern = r"ran\. \((\d+)\s*ms total\)"
        match = re.search(pattern, output)
        if match:
            ms = int(match.group(1))
            return ms / 1000.0
        return -1.0
    elif framework == "catch":
        pattern = rf"(\d+\.\d+)\s+s:\s+{re.escape(test_name)}"
        match = re.search(pattern, output)
        if match:
            return float(match.group(1))
        return -1.0
    elif framework == "doctest":
        #pattern = rf"\[{re.escape(test_name)}\]\s+passed\s+in\s+(\d+\.\d+)s"
        #pattern = rf"{re.escape(test_name)}.*\((\d+\.\d+)s\)"
        #match = re.search(pattern, output)
        #if match:
        #    return float(match.group(1))
        if "Status:" in output and "SUCCESS" in output:
            return 0.0
        else:
            return -1.0
    elif framework == "boost":
        pattern = rf"{re.escape(test_name)}.*passed in (\d+\.\d+) sec"
        match = re.search(pattern, output)
        if match:
            return float(match.group(1))
        return -1.0
    elif framework == "qt":
        pattern = rf"PASS\s*:\s*{re.escape(test_name)}\s*\((\d+\.\d+)\s*seconds\)"
        match = re.search(pattern, output)
        if match:
            return float(match.group(1))
        return -1.0
    else:
        raise ValueError(f"Unknown framework {framework}")


def parse_ctest_output(output: str) -> dict[str, Union[int, float]]:
    """Parse CTest output text to extract key test statistics."""
    stats: dict[str, Union[int, float]] = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "total": 0,
        "total_time_sec": 0.0,
        "pass_rate": 0,
    }

    m = re.search(r"(\d+)% tests passed,\s*(\d+)\s*tests failed out of\s*(\d+)", output)
    if m:
        pass_rate, failed, total = map(int, m.groups())
        passed = total - failed
        stats.update({
            "passed": passed,
            "failed": failed,
            "total": total,
            "pass_rate": pass_rate
        })

    m = re.search(r"(\d+)\s*tests skipped", output)
    if m:
        stats["skipped"] = int(m.group(1))

    m = re.search(r"Total Test time \(real\)\s*=\s*([\d\.]+)\s*sec", output)
    if m:
        stats["total_time_sec"] = float(m.group(1))

    return stats

def parse_single_ctest_output(output: str, previous_results: dict[str, dict[str, list[float]]] = {}) -> dict[str, dict[str, list[float]]]:
    """
    Parse ctest output into a dictionary mapping test names to a list of runtimes.

    Args:
        output (str): The raw ctest output as a string.
        previous_results (dict, optional): A previous dictionary to merge with.

    Returns:
        dict: {test_name: [times]}
    """

    if not previous_results:
        results: dict[str, dict[str, list[float]]] = defaultdict(dict)
    else:
        results: dict[str, dict[str, list[float]]] = defaultdict(dict, {k: v for k, v in previous_results.items()})

    patterns = [
        # pattern 1: [OK] test_name (time ms)
        r"\[\s*OK\s*\]\s*(.+?)\s*\((\d+)\s*ms\)",
        
        # pattern 2: time s: test_name
        r"(\d+\.\d+)\s+s:\s+(.+)",

        # pattern 3: [test_name] passed in time s
        r"\[(.+?)\]\s+passed\s+in\s+(\d+\.\d+)s",

        # pattern 4: test_name passed in time sec
        r"(.+?)\s+passed\s+in\s+(\d+\.\d+)\s+sec",

        # pattern 5: PASS : test_name (time seconds)
        r"PASS\s*:\s*(.+?)\s*\((\d+\.\d+)\s*seconds\)",

        # pattern 6: Test #number: test_name ... Passed time sec
        r"Test\s+#\d+:\s+([\w\.\-]+)\s+.*Passed\s+([\d\.]+)\s+sec",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, output):
            if pattern == patterns[1]:
                # pattern 2 swaps order: time, then test name
                time = float(match.group(1))
                test_name = match.group(2)
            else:
                test_name = match.group(1)
                time = match.group(2)

            if not results[test_name]:
                results[test_name] = {'parsed': [], 'time': []}

            # Normalize time to seconds (convert ms to seconds if needed)
            if "ms" in pattern:
                time = int(time) / 1000.0
            else:
                time = float(time)
            
            results[test_name]['parsed'].append(time)
            results[test_name]['time'].append(time)

    return dict(results)

def parse_usr_bin_time(output: str) -> float:
    match = re.search(r'(\d+)\s*ms', output, re.MULTILINE)
    if match:
        real_ms = int(match.group(1))
        real_seconds = real_ms / 1000.0
        return real_seconds
    return 0.0


def remove_exclude_from_all(repo_root: Path) -> None:
    cmake_files = list(repo_root.rglob("CMakeLists.txt"))

    pattern = re.compile(r'\bEXCLUDE_FROM_ALL\b')

    for cmake_file in cmake_files:
        original = cmake_file.read_text(encoding="utf-8")

        if "EXCLUDE_FROM_ALL" not in original:
            continue

        modified = pattern.sub("", original)

        if modified != original:
            cmake_file.write_text(modified, encoding="utf-8")
