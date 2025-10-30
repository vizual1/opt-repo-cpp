import os
from typing import Any
from datetime import datetime, timezone

storage: dict[str, str] = {
    "popular": os.path.join("data", "popular_urls.txt"),
    "commits": os.path.join("data", "commits"),
    "performance": os.path.join("data", "performance"),
    "repos": os.path.join("data", "repo_urls.txt"),
    
    "store_analyze": "data/analyze",
    
    "results": "data/results.txt",
    "cmake-dep": "cache/cmake-dep.json",
}

commits: dict[str, Any] = {
    # select commits since -> until
    'since': datetime(2024, 1, 1, tzinfo=timezone.utc),
    'until': datetime.now(timezone.utc),
    
    'min-exec-time-improvement': 0.05,
    'min-p-value': 0.05
}

llm: dict[str, Any] = {
    'cache_file': 'cache/commit.json',
    'api_key': os.environ['api_key'],
    'base': True,
    'base_url': 'https://openrouter.ai/api/v1',
    'model': 'openai/gpt-4.1-nano', #'moonshotai/kimi-k2:free', #'openai/gpt-oss-20b:free' #'deepseek/deepseek-chat-v3.1:free' #'z-ai/glm-4.5-air:free'

    'ollama': True, 
    'ollama_stage1_model': "qwen2.5:7b-instruct-q4_K_M",
    'ollama_stage2_model': "codellama:7b-instruct", #"codellama:13b-instruct",
    'ollama_resolver_model': "qwen2.5:7b-instruct-q4_K_M",
    #'ollama_model': "mistral", # "phi3:mini" # "qwen2.5:7b-instruct-q4_K_M"
    'ollama_url': "http://127.0.0.1:11434/api/generate", #"http://host.docker.internal:11434/api/generate", 

    # <name> for repository name and <message> for commit message to be filtered
    'stage1': 
     """The following is the message of a commit in the <name> repository:
        ###Message Start###<message>###Message End###
        How likely is it for this commit to be a performance improving commit in terms of execution time? 
        Answer strictly by only writing the likelihood in the following format:
        Likelihood: x%""",
    'stage2':
     """The following is the message of a commit in the <name> repository:\n\n###Message Start###<message>\n###Message End###"
          \n\nThe diff of the commit is:\n\n###Diff Start###<diff>\n###Diff End###
          \n\nIs this commit a performance improving commit in terms of execution time? 
         Answer strictly with 'YES' or 'NO'."""
}

github: dict[str, str] = {
    'access_token': os.environ['access_token']
}

likelihood: dict[str, int] = {
    'min_likelihood': 50,
    'max_likelihood': 90
}

testing: dict[str, Any] = {
    # filters repositories and commits by target_link_libraries with gtest, catch2, doctest, etc.
    "no_list_testing": True,
    # number of times to tests the commits (warmup + commit_test_times)
    "warmup": 1,
    "commit_test_times": 5,
}

resolver: dict[str, str] = {
    # <deps> for list of dependencies to generate json for
    'resolver_message': 
     """You are an expert in CMake, Ubuntu, and vcpkg. 
        Given one or more missing dependency names, return a single JSON object where each key is a <dependency>:
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
        1. Use correct subfolders (e.g. '/usr/include/SDL2', '/usr/include/freetype2').
        2. Mirror subfolder in vcpkg under '/opt/vcpkg/installed/x64-linux/include'.
        3. Output only valid JSON (no text)
        4. For unknown deps, set "<Ubuntu 22.04 package>" and "<vcpkg port>" to "".
        5. Generate it for all <dependency> in <deps>.
        """
}

test_flags_filter: dict[str, list[str]] = {
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

valid_test_dir: set[str] = {
    'test', 'tests', 'unittest', 'unittests', 
    'src/test', 'src/tests', 'src/unittest', 'src/unittests'
}

# mapping of cmake_minimum_required -> ubuntu version -> docker image
docker_map: dict[str, str] = {
    "ubuntu:24.04": "cpp24",
    "ubuntu:22.04": "cpp22",
    "ubuntu:20.04": "cpp20",
    "ubuntu:18.04": "cpp18",
    "ubuntu:16.04": "cpp18"
}


TEST_KEYWORDS = [
    "test", "tests", "unittest", "unittests", "testing",

    "gtest", "googletest",
    "integration_tests",
    "benchmark", "perf", "gperf"
]

