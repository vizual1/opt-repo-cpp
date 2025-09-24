import os
from typing import Any

storage: dict[str, str] = {
    "dataset": "data",
    "repo_urls": "repo_urls.txt",
    "history": "history.txt",
    "filtered": "filtered.txt",
    "results": "results.txt"
}

llm: dict[str, Any] = {
    'cache_file': 'test',
    'api_key': os.environ['api_key'],
    'base': True,
    'base_url': 'https://openrouter.ai/api/v1',
    'model': 'z-ai/glm-4.5-air:free'
}
# openai/gpt-oss-120b:free

github: dict[str, str] = {
    'access_token': os.environ['access_token']
}

likelihood: dict[str, int] = {
    'min_likelihood': 50,
    'max_likelihood': 50
}

# TODO: flags
FLAG_KEYWORDS = [
    "BUILD_TESTING", "ENABLE_TESTING", "WITH_TESTING", "UNIT_TESTING", "COMPILE_TESTING",
    "BUILD_TESTS", "BUILD_TEST", "ENABLE_TESTS", "ENABLE_TEST","WITH_TESTS", "WITH_TEST", 
    "COMPILE_TESTS", "COMPILE_TEST", "TESTS", "TEST",
    "BUILD_UNIT_TESTS", "ENABLE_UNIT_TESTS", "WITH_UNIT_TESTS", "UNIT_TESTS", "UNITTESTS",
    "BUILD_UNIT_TEST", "ENABLE_UNIT_TEST", "WITH_UNIT_TEST", "UNIT_TEST", "UNITTEST", 
    "RUN_TESTS", "TESTING"
]

TEST_DIR = {
    'test', 'tests', 'unittest', 'unittests', 
    'src/test', 'src/tests', 'src/unittest', 'src/unittests',

    "gtest", "googletest",
    "integration_tests",
    "benchmark", "perf", "gperf"
}


TEST_KEYWORDS = [
    "test", "tests", "unittest", "unittests", "testing",

    "gtest", "googletest",
    "integration_tests",
    "benchmark", "perf", "gperf"
]