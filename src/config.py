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
FLAG_BASE = [
    "BUILD_TESTING", "ENABLE_TESTING", "WITH_TESTING", "UNIT_TESTING", "COMPILE_TESTING",
    "BUILD_TESTS", "BUILD_TEST", "ENABLE_TESTS", "ENABLE_TEST","WITH_TESTS", "WITH_TEST", 
    "COMPILE_TESTS", "COMPILE_TEST", "TESTS", "TEST",
    "BUILD_UNIT_TESTS", "ENABLE_UNIT_TESTS", "WITH_UNIT_TESTS", "UNIT_TESTS", "UNITTESTS",
    "BUILD_UNIT_TEST", "ENABLE_UNIT_TEST", "WITH_UNIT_TEST", "UNIT_TEST", "UNITTEST", 
    "RUN_TESTS", "TESTING"
]
#FLAG_KEYWORDS = ["\b" + flag for flag in FLAG_BASE] + ["_" + flag for flag in FLAG_BASE]
FLAG_KEYWORDS = [rf"\b{flag}\b" for flag in FLAG_BASE] + [rf"_{flag}\b" for flag in FLAG_BASE]

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

PYTHON_MAP = {
    "libmultiprocess": "Python module, install via pip if needed",
    "libmultiprocessnative": "Python module, install via pip if needed",
    "libmultiprocess": "Python module, install via pip if needed",
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
    "flexiblas_api": "Install FlexiBLAS manually or via Intel oneAPI MKL"
}

SKIP_NAMES = {
    "threads", "openmp", "pkgconfig", "required", "quiet", "lib", "none", "all", "bin", "interpreter", "names", "imported_target", "sw", "${package}",
    "data", "utils", "base", "common"
}