import re
from typing import Union

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