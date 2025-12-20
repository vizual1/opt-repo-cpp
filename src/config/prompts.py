STAGE1_PROMPT = """The following is a commit in the <name> repository:

The following is the commit message that fixes this issue:

###Commit Message###<message>###Commit Message End###

Question: Is this commit likely related to improving execution time?"""


DIFF_PROMPT = """The following is the diff of a commit in the <name> repository:

###Diff Patch###<diff>###Diff Patch End###

Question: Does this diff patch likely improve execution time?
"""

STAGE2_PROMPT = """The following is the commit message in the <name> repository:

###Commit Message###<message>###Commit Message End###

The following is the diff:

###Diff Start###<diff>###Diff End###

Question: Is this issue likely related to improving execution time?"""

RESOLVER_PROMPT =  """You are an expert in CMake, Ubuntu, and vcpkg. 

Given one or more missing dependency names, return a single JSON object where each key is a <dependency>:
{{
"<dependency>": {{
    "apt": "<Ubuntu 24.04 packages or libraries>",
    "vcpkg": "<vcpkg port>"
}}
}}
Rules:
1. Use correct libraries and package names for Ubuntu 24.04 if possible otherwise for Ubuntu 22.02.
2. If there are multiple possible libraries and packages, then put them into an array ["library1", "library2", ...].
3. Output only valid JSON (no text)
4. For unknown deps, set "<Ubuntu 24.04 packages or libraries>" and "<vcpkg port>" to "".
5. Generate it for all <dependency> in <deps>.
"""