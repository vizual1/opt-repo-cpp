STAGE1_PROMPT = """The following is an issue in the <name> repository:

The following is the commit message that fixes this issue:

###Commit Message###<message>###Commit Message End###



Question: Is this issue likely related to improving execution time?"""

# Answer strictly in this JSON format (do not add any explanation):
# {"answer": "yes"} or {"answer": "no"}.

STAGE2_PROMPT = """The following is the commit message in the <name> repository:

###Commit Message###<message>###Commit Message End###

The following is the diff:

###Diff Start###<diff>###Diff End###

Answer strictly in this JSON format (do not add any explanation):
{"answer": "yes"} or {"answer": "no"}.

Question: Is this issue likely related to improving execution time?"""

RESOLVER_PROMPT =  """You are an expert in CMake, Ubuntu, and vcpkg. 

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