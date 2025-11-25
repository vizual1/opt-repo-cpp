from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path("data")
CACHE_DIR = Path("cache")

STORAGE_PATHS = {
    "popular": DATA_DIR / "popular_urls.txt",
    "commits": DATA_DIR / "performance" / "filtered.txt",
    "performance": DATA_DIR / "performance",
    "repos": DATA_DIR / "repo_urls.txt",
    "store_analyze": DATA_DIR / "analyze",
    "results": DATA_DIR / "results.txt",
    "cmake-dep": CACHE_DIR / "cmake-dep.json",
}

COMMIT_TIME = {
    'since': datetime(2020, 1, 1, tzinfo=timezone.utc),
    'until': datetime.now(timezone.utc),
    'min-exec-time-improvement': 0.05,
    'min-p-value': 0.05
}

TEST_KEYWORDS = [
    "test", "tests", "unittest", "unittests", "testing",
    "gtest", "googletest", "integration_tests",
    "benchmark", "perf", "gperf"
]

VALID_TEST_DIRS = {
    'test', 'tests', 'unittest', 'unittests', 'bench',
    'src/test', 'src/tests', 'src/unittest', 'src/unittests'
}

VALID_TEST_FLAGS: dict[str, list[str]] = {
    "valid": [
        "BUILD_TESTING", "BUILD_TESTS", "BUILD_TEST",
        "ENABLE_TESTING", "ENABLE_TESTS", "ENABLE_TEST",
        "ENABLE_UNITTESTS",
        "WITH_TESTING", "WITH_TESTS",
        "WITH_UNIT_TESTS",
        "BUILD_UNIT_TESTS",
        "TESTING", "TESTS", "TEST",
        "RUN_TESTS"
    ],
    "prefix": [],
    "suffix": [
        "_BUILD_TEST", "_BUILD_TESTS", "_BUILD_TESTING",
        "_ENABLE_TEST", "_ENABLE_TESTS", "_ENABLE_TESTING",
        "_UNIT_TESTS", "_UNITTEST"
    ],
    "in": [
        "_UNIT_TEST_"
    ]
}


DOCKER_IMAGE_MAP = {
    "ubuntu:24.04": "cpp24",
    "ubuntu:22.04": "cpp22",
    "ubuntu:20.04": "cpp20",
    "ubuntu:18.04": "cpp18",
    "ubuntu:16.04": "cpp18"
}