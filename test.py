import json, subprocess
from pathlib import Path
from src.utils.image_handling import image

PYTHON_EXEC = "python3"

def test_collect():
    cmd = [PYTHON_EXEC, "main.py", "--collect", "--repos=3", "--stars=1000"]
    subprocess.run(cmd, check=True)

    collect = Path("data/collect.txt")
    with open(collect, 'r') as f:
        lines1 = f.readlines()
    assert len(lines1) == 3
    testcollect = Path("data/testcollect.txt")
    if testcollect.exists():
        with open(testcollect, 'r') as f:
            lines2 = f.readlines()
    else:
        lines2 = []
    fail = Path("data/fail.txt")
    if fail.exists():
        with open(fail, 'r') as f:
            lines3 = f.readlines()
    else:
        lines3 = []
    assert len(lines1) == 3 and len(lines2 + lines3) == 3
    print("TEST (--collect) 1 SUCCESSFUL")
    testcollect.unlink(True)
    fail.unlink(True)
    
    blacklist = collect.rename("data/blacklist.txt")

    cmd = [PYTHON_EXEC, "main.py", "--collect", "--repos=3", "--stars=1000", "--blacklist=data/blacklist.txt"]
    subprocess.run(cmd, check=True)

    collect = Path("data/collect.txt")
    with open(collect, 'r') as f:
        lines1 = f.readlines()
    assert len(lines1) == 3
    with open(blacklist, 'r') as f:
        lines2 = f.readlines()
    assert not set(lines1).intersection(set(lines2))
    print("TEST (--collect) 2 SUCCESSFUL")
    blacklist.unlink(True)
    collect.unlink(True)

    cmd = [PYTHON_EXEC, "main.py", "--testcollect", "--input=data/test/test_repositories.txt"]
    subprocess.run(cmd, check=True)

    testcollect = Path("data/testcollect.txt")
    if testcollect.exists():
        with open(testcollect, 'r') as f:
            lines = f.readlines()
    else:
        lines = []
    assert len(lines) == 1
    print("TEST (--collect) 3 SUCCESSFUL")
    testcollect.unlink(True)


def test_commits():
    cmd = [PYTHON_EXEC, "main.py", "--commits", "--filter=simple", "--input=data/test/test_repositories.txt", "--limit=3"]
    subprocess.run(cmd, check=True)

    filtered_commits = Path("data/filtered_commits.txt")
    assert filtered_commits.exists()
    print("TEST (--commits) 1 SUCCESSFUL")
    filtered_commits.unlink()

    cmd = [PYTHON_EXEC, "main.py", "--commits", "--test", "--filter=simple", "--input=data/test/test_repositories.txt", "--limit=3", "--noimage"]
    subprocess.run(cmd, check=True)

    filtered_commits = Path("data/filtered_commits.txt")
    assert filtered_commits.exists()
    print("TEST (--commits) 2 SUCCESSFUL")
    filtered_commits.unlink()

    json_files = list(Path("data/commits/").glob("*.json"))
    assert json_files
    assert len(json_files) == 3
    for file in json_files:
        file.unlink()
    print("TEST (--commits) 3 SUCCESSFUL")

    cmd = [PYTHON_EXEC, "main.py", "--testcommits", "--input=data/test/test_commits.txt", "--noimage"]
    subprocess.run(cmd, check=True)

    json_files = list(Path("data/commits/").glob("*.json"))
    assert json_files
    assert len(json_files) == 2
    for file in json_files:
        file.unlink()
    print("TEST (--commits) 4 SUCCESSFUL")

def test_docker():
    image = "madmann91_bvh_1b2472a44e22fcf7dc921b7eb36b7729ec97e8b5"
    cmd = [PYTHON_EXEC, "main.py", "--genimages", f"--input=data/test/"]
    subprocess.run(cmd, check=True)

    cmd = ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    images = result.stdout.strip().split("\n")
    assert f"{image}:latest" in images
    print("TEST (--genimages) SUCCESSFUL")

    cmd = [PYTHON_EXEC, "main.py", "--testdocker", f"--docker={image}"]
    subprocess.run(cmd, check=True)

    json_files = list(Path("data/commits/").glob("*.json"))
    assert json_files and len(json_files) == 1
    json_tests = list(j.stem for j in Path("data/test/").glob("*.json"))
    for file in json_files:
        assert file.stem in json_tests
        assert f"{file.stem}:latest" in images
        cmd = ["docker", "rmi", image]
        subprocess.run(cmd, check=True)
        file.unlink()
    print("TEST (--testdocker) 1 SUCCESSFUL")

    cmd = [PYTHON_EXEC, "main.py", "--pullimages", f"--input=data/test/"]
    subprocess.run(cmd, check=True)
    cmd = ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    images = result.stdout.strip().split("\n")
    assert f"{image}:latest" in images
    print("TEST (--pullimages) SUCCESSFUL")

    cmd = [PYTHON_EXEC, "main.py", "--testdocker", f"--docker={image}"]
    subprocess.run(cmd, check=True)

    json_files = list(Path("data/commits/").glob("*.json"))
    assert json_files
    json_tests = list(j.stem for j in Path("data/test/").glob("*.json"))
    for file in json_files:
        assert file.stem in json_tests
        assert f"{file.stem}:latest" in images
        file.unlink()
    print("TEST (--testdocker) 2 SUCCESSFUL")

    cmd = [PYTHON_EXEC, "main.py", "--testpatch", f"--docker={image}", f"--diff=data/test/{image}.patch"]
    subprocess.run(cmd, check=True)
    json_files = list(Path("data/commits/").glob("*.json"))
    assert json_files
    json_tests = list(j.stem for j in Path("data/test/").glob("*.json"))
    for file in json_files:
        assert file.stem in json_tests
        cmd = ["docker", "rmi", image, f"tommyho1999/opt-repo-cpp:{image}"]
        subprocess.run(cmd, check=True)
        file.unlink()
    print("TEST (--testpatch) SUCCESSFUL")

    

def test_llm():
    assert False
    
    
def main() -> None:
    test_collect()
    test_commits()
    test_docker()

if __name__ == '__main__':
    main()
