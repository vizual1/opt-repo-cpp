import os
from typing import Any

storage: dict[str, str] = {
    "store_commits": os.path.join("data", "commits"),
    "store_analyze": "data/analyze",
    "repo_urls": "data/analyze/cpp-base.txt",
    "results": "data/results.txt",
    "cmake-dep": "cache/cmake-dep.json"
}

llm: dict[str, Any] = {
    'cache_file': 'cache/save.txt',
    'api_key': os.environ['api_key'],
    'base': True,
    'base_url': 'https://openrouter.ai/api/v1',
    'model': 'openai/gpt-4.1-nano', #'moonshotai/kimi-k2:free', #'openai/gpt-oss-20b:free' #'deepseek/deepseek-chat-v3.1:free' #'z-ai/glm-4.5-air:free'

    'ollama': True, 
    'ollama_model': "mistral", # "phi3:mini" # "qwen2.5:7b-instruct-q4_K_M"
    'ollama_url': "http://host.docker.internal:11434/api/generate", # "http://127.0.0.1:11434/api/generate"

    'twostage': False,
    # <name> for repository name and <message> for commit message to be filtered
    'message1': 
     """The following is the message of a commit in the <name> repository: 
        ###Message Start###<message>###Message End###
        Does this commit likely improve performance  in terms of execution time?
        Answer ONLY: Yes or No""",
    'message2': 
     """The following is the message of a commit in the <name> repository:
        ###Message Start###<message>###Message End###
        How likely is it for this commit to be a performance improving commit in terms of execution time? 
        Answer by only writing the likelihood in the following format for x: int with no comments:
        Likelihood: x%""",
    'message3':
     """The following is the message of a commit in the <name> repository:\n\n###Message Start###<message>\n###Message End###"
          \n\nThe diff of the commit is:\n\n###Diff Start###<diff>\n###Diff End###
          \n\nIs this commit a performance improving commit in terms of execution time? 
         Answer with 'YES' or 'NO'."""
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
    # number of times to tests the commits
    "commit_test_times": 3,
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
        5. Generate it for all <dependency> if exists in <deps>.
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

docker_map: dict[str, str] = {
    "ubuntu:24.04": "cpp-base",
    "ubuntu:22.04": "cpp-base",
    "ubuntu:20.04": "cpp-base",
    "ubuntu:18.04": "cpp-base",
    "ubuntu:16.04": "cpp-base"
}


TEST_KEYWORDS = [
    "test", "tests", "unittest", "unittests", "testing",

    "gtest", "googletest",
    "integration_tests",
    "benchmark", "perf", "gperf"
]

"""
PACKAGE_MAP = {
    "openssl": "libssl-dev",
    "zlib": "zlib1g-dev",
    "fmt": "libfmt-dev",
    "spdlog": "libspdlog-dev",
    "protobuf": "libprotobuf-dev",
    "curl": "libcurl4-openssl-dev",
    "openblas": "libopenblas-dev",
    "openblas64": "libopenblas64-dev",
    "blas": "libblas-dev",
    "blas-atlas": "libatlas-base-dev",
    "dnnl": "libdnnl-dev",
    "vulkan": "libvulkan-dev",
    "sqlite3": "libsqlite3-dev",
    "tbb": "libtbb-dev",
    "png": "libpng-dev",
    "opencl": "ocl-icd-opencl-dev",
    "blis": "libblis-dev",
    "flexiblas_api": "libflexiblas-dev",
    "openmp": "libomp-dev",
    "doxygen": "doxygen",
    "dot": "graphviz",
    "libtiff": "libtiff-dev",
    "tiff": "libtiff-dev",
    "icu-uc": "libicu-dev",
    "icu-i18n": "libicu-dev",
    "i18n": "libicu-dev",
    "uc": "libicu-dev",
    "pangocairo": "libpango1.0-dev",
    "pango": "libpango1.0-dev",
    "pangoft2": "libpango1.0-dev",
    "cairo": "libcairo2-dev",
    "fontconfig": "libfontconfig1-dev",
    "libarchive": "libarchive-dev",
    "fontconfig": "libfontconfig1-dev",
    "gtest": "libgtest-dev",
    "icu": "libicu-dev",
    "lept": "libleptonica-dev",
    "libcurl": "libcurl4-gnutls-dev",
    "glfw3": "libglfw3-dev",
    "glfw": "libglfw3-dev",
    "capstone": "libcapstone-dev",
    "yara": "libyara-dev",
    "yara-dev": "libyara-dev",
    "freetype": "libfreetype6-dev",
    "mbedtls": "libmbedtls-dev",
    "libssh2": "libssh2-1-dev",
    "x11": "libx11-dev",
    "qt6": "qt6-base-dev",
    "widgets": "qt6-base-dev",
    "multimedia": "qt6-multimedia-dev",
    "core": "qt6-base-dev",
    "webp": "libwebp-dev",
    "libavif": "libavif-dev", 
    "libtommath": "libtommath-dev", 
    "sdl2": "libsdl2-dev",
    "ffmpeg": "libavcodec-dev",
}

NON_APT = {
    "python3": "Ensure Python 3 interpreter is installed",
    "cudatoolkit": "Install NVIDIA CUDA toolkit manually",
    "rocblas": "Use AMD ROCm libraries",
    "hipblas": "Use AMD ROCm libraries",
    "mkl": "Use Intel oneAPI MKL",
    "mkl-sdl": "Use Intel oneAPI MKL",
    "musatoolkit": "Likely vendor-provided, not on apt",
    "ggml": "Provided by llama.cpp itself",
    "llama": "Project-specific (llama.cpp)",
    "dawn": "Google Dawn WebGPU SDK (build from source)",
    "onemath": "Intel OneMath library (part of oneAPI)",
    "glslc": "Install Vulkan SDK (shader compiler)",
    "hip": "Use AMD HIP/ROCm libraries",
    "intelsycl": "Install Intel oneAPI DPC++/SYCL SDK",
    "cpufeaturesndkcompat": "Project-specific / Android NDK library. Install via NDK or project source.",
    "miniaudio": "Header-only library, usually included in project",
    "edlib": "Header-only or vendored library, install manually if needed",
    "coreclrembed": "Project-specific library, install/build manually",
    "hwy": "Highway hashing library, manual build",
    "libwoff2dec": "WOFF2 font decoder, manual build",
    "swifttesting": "Project-specific testing library",
    "angle": "ANGLE graphics library, manual build",
    "simdutf": "SIMD UTF library, manual build",
    "mman": "Part of system libc, skip installation",
    "openvino": "Intel OpenVINO toolkit. Install manually from Intel's site.",
    "Runtime": "Part of SDK or project-specific runtime. Install manually.",
    "flexiblas_api": "Install FlexiBLAS manually or via Intel oneAPI MKL",
    "libmultiprocess": "Python module, install via pip if needed",
    "libmultiprocessnative": "Python module, install via pip if needed",
    "libmultiprocess": "Python module, install via pip if needed",
}

SKIP_NAMES = {
    "threads", "openmp", "pkgconfig", "required", "quiet", "lib", "none", "all", "bin", "interpreter", "names", "imported_target", "sw", "${package}",
    "data", "utils", "base", "common"
}
"""