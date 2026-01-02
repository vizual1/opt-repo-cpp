CONFIG_ERROR_PATTERNS = [
    r"No package '([a-zA-Z0-9_\-\+\.]+)' found",
    r"Could NOT find ([A-Za-z0-9_\-\+\.]+)",
    r"Could not find ([A-Za-z0-9_+-]+)",
    r"Could not find ([A-Za-z0-9_\-\+\.]+), missing",
    r"Could not find a package configuration file provided by \"([^\"]+)\"",
    r"Could not find a configuration file for package \"([^\"]+)\"",
    r"([A-Za-z0-9_\-\+\.]+)\s+package NOT found",
    r"No module named ['\"]([^'\"]+)['\"]",
    r"executable '([a-zA-Z0-9_\-\+\.]+)' not found",
    r"Package '([a-zA-Z0-9_\-\+\.]+)'.*not found",
    r"package '([^']+)' not found",
    r"Dependency '([^']+)' is required but was not found",
    r"Failed to find ([A-Za-z0-9_\-\+\.]+)",
    r"Looking for ([A-Za-z0-9_\-\+\.]+) - not found",
    r"Dependency ([A-Za-z0-9_\-\+\.]+) not found",
    r"  ([A-Za-z0-9_\-\+\.]+) is required",
    r'([A-Z0-9_]+)_(?:INCLUDE_DIR|LIBRARIES)-NOTFOUND',
    r"Please install the ([a-zA-Z0-9_\-\+\.]+) library package",
    r"Requires ([a-zA-Z0-9_\-\+\.]+) >=",
    r"([A-Za-z0-9_+\-]+)\s+component not found",
    r"Can't find .*?of\s+([^\s]+)",
    r"Unable to find requested ([A-Za-z0-9_+-]+) installation",
    r"Unable to locate ([A-Za-z0-9_+\-]+) include",
    r"  ([A-Za-z0-9_+\-]+) not found",
    r"  ([A-Za-z0-9_+\-]+) library not found",
    r"None of the required '([A-Za-z0-9_+-]+)",
    r"  ([A-Za-z0-9_+-]+)\s+library missing",
    r'references the file\s+"([^"]+)"',
    r'([A-Z]+)_INCLUDE_DIR',
    r'-D([A-Z]+)_INCLUDE_PATH',
    r' component\s+"([^"]+)"',
    r"The following required packages were not found:\s*(?:\n\s*-\s*([^\s]+))+"
]

BUILD_ERROR_PATTERNS = [
    r"fatal error:\s+([\w_]+\.h):\s+No such file or directory",
    r"fatal error:\s+([\w_/]+\.h):\s+No such file or directory",
    r"cannot find -l([\w_]+)",
    r"(?:^|[\s:])([\w.+-]+):\s+(?:not found|command not found|No such file or directory)"
]

FLAGS_ERROR_PATTERNS = [
    {
        "name": "Generic GCC attribute warnings under -Werror",
        "regex": r"[-]W(ignored|array-bounds|stringop|attributes)",
        "action": lambda append, remove, command, match: append.update([
            "-DCMAKE_CXX_FLAGS=-Wno-error",
        ]),
    },
    {
        "name": "Dangling reference warning under -Werror",
        "regex": r"dangling-reference",
        "action": lambda append, remove, command, match: append.update([
            "-DCMAKE_CXX_FLAGS=-Wno-error"
        ]),
    },
    {
        "name": "Catch2 SIGSTKSZ constexpr error",
        "regex": r"storage size of 'altStackMem' isn't constant|sysconf",
        "action": lambda append, remove, command, match: append.update([
            "-DSIGSTKSZ=16384"
        ]),
    },
    {
        "name": "Older versions of Catch2 incorrectly used it inside a constexpr expression",
        "regex": r"non-'constexpr' function 'sysconf'|altStackMem",
        "action": lambda append, remove, command, match: append.update([
            "-DUSE_SYSTEM_CATCH2=ON",
            "-DCATCH_USE_SYSTEM=ON",
        ])
    },
    {
        "name": "FetchContent: Failed to checkout tag",
        "regex": r"failed to checkout tag",
        "action": lambda append, remove, command, match: append.update([
            "-DFETCHCONTENT_TRY_FIND_PACKAGE_MODE=ALWAYS",
            "-DFETCHCONTENT_UPDATES_DISCONNECTED=ON",
            "-DFETCHCONTENT_FULLY_DISCONNECTED=OFF",
        ]),
    },
    {
        "name": "FetchContent: Git clone failure",
        "regex": r"(fatal: .*unable to access|could not clone|timeout|operation timed out)",
        "action": lambda append, remove, command, match: append.update([
            "-DFETCHCONTENT_UPDATES_DISCONNECTED=ON",
            "-DFETCHCONTENT_FULLY_DISCONNECTED=ON",
        ]),
    },
    {
        "name": "Don't use CMAKE_BUILD_TYPE",
        "regex": r"Don't use CMAKE_BUILD_TYPE",
        "action": lambda append, remove, command, match: (
            command.add("-DCMAKE_BUILD_TYPE=Debug")
        ),
    },
    {
        "name": "Requires C++14",
        "regex": r"(C\+\+14|requires at least c\+\+14|std::make_unique.*not declared)",
        "action": lambda append, remove, command, match: append.update([
            "-DCMAKE_CXX_STANDARD=14",
            "-DCMAKE_CXX_STANDARD_REQUIRED=ON",
        ]),
    },
    {
        "name": "Requires C++17",
        "regex": r"(filesystem|optional|variant|any).*not.*member",
        "action": lambda append, remove, command, match: append.update([
            "-DCMAKE_CXX_STANDARD=17",
            "-DCMAKE_CXX_STANDARD_REQUIRED=ON",
        ]),
    },
    {
        "name": "Requires C++20",
        "regex": r"(ranges|concepts|coroutine|format).*not.*member",
        "action": lambda append, remove, command, match: append.update([
            "-DCMAKE_CXX_STANDARD=20",
            "-DCMAKE_CXX_STANDARD_REQUIRED=ON",
        ]),
    },
    {
        "name": "CXX Compiler missing",
        "regex": r"(no cmake_cxx_compiler|cxx compiler identification is unknown)",
        "action": lambda append, remove, command, match: append.add(
            "-DCMAKE_CXX_COMPILER=g++"
        ),
    },
    {
        "name": "Clang recommended instead of GCC",
        "regex": r"clang.*recommended|gcc.*unsupported version",
        "action": lambda append, remove, command, match: append.add(
            "-DCMAKE_CXX_COMPILER=usr/bin/clang++"
        ),
    },
    {
        "name": "",
        "regex": r'cmake\s+(-D[\w_]+=OFF)',
        "action": lambda append, remove, command, match: (
            append.add(match.group(1)),
            remove.add(match.group(1).replace("=OFF", "=ON")),
        )
    }
]
