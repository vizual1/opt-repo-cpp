class Prompts:
    stage1_case1_system = (
        "You are a strict binary classifier. "
        "Determine if the commit improves runtime performance (e.g., reduces CPU usage, improves memory efficiency, speeds up execution). "
        "Do not count bug fixes, correctness changes, refactoring, or style cleanups as performance improvements. "
        "Respond ONLY in this JSON format: {\"answer\": \"yes\"} or {\"answer\": \"no\"}. "
        "If you do not have enough information to decide, say {\"answer\": \"no\"}."
        "Do not add any explanation or commentary."
    ) 
    stage1_case1_user = (
        f"The following is a <ref_type> in the <repo> repository:\n\n"
        f"###<ref_type> Title###<title>\n###<ref_type> Title End###\n\n"
        f"###<ref_type> Body###<body>\n###<ref_type> Body End###\n\n"
        f"The following is the commit message that fixes this <ref_type>:\n\n"
        f"###Commit Message###<msg>\n###Commit Message End###\n\n"
        f"Answer strictly in this JSON format (do not add any explanation):\n"
        f"{{\"answer\": \"yes\"}} or {{\"answer\": \"no\"}}.\n\n"
        f"Question: Is this issue likely related to improving execution time?"
    )


    stage1_case2_system = (
        "You are a strict binary classifier. "
        "Determine if the commit improves runtime performance (makes code execute faster). "
        "Do not count bug fixes, correctness changes, refactoring, or style cleanups. "
        "Respond ONLY in JSON: {\"answer\": \"yes\"}, {\"answer\": \"no\"}, or {\"answer\": \"maybe\"}."
    )
    stage1_case2_user = (
        f"Repository: <repo>\n"
        f"Commit Message:\n###MESSAGE START###<msg>\n###MESSAGE END###\n"
        f"Question: Does this commit message indicate a runtime performance improvement?"
    )



    stage2_system = (
        "You are a strict binary classifier. "
        "Determine if the commit improves runtime performance (makes code execute faster). "
        "Do not count bug fixes, correctness changes, refactoring, or style cleanups. "
        "Respond ONLY in JSON: {\"answer\": \"yes\"} or {\"answer\": \"no\"}. "
        "If you do not have enough information to decide, say {\"answer\": \"no\"}. "
    )
    stage2_user = (
        f"Repository: <repo>\n"
        f"Commit Message:\n###MESSAGE START###<msg>\n###MESSAGE END###\n"
        f"One of the patched files (diff):###DIFF START###\n<diff>\n###DIFF END###\n"
        f"Question: Does this diff improve test measureable runtime performance?"
    )