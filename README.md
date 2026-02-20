# C++ Repository Automation Tool

A Python-based tool to collect C++ repositories from GitHub, gather commits, apply filtering, and run automated testing in Docker environments.

---

## Features
- **Repository Collection**: Crawl GitHub for C++ repositories with customizable filters
- **Commit Analysis**: Filter and analyze commits using LLMs
- **Automated Testing**: Run tests in isolated Docker environments
- **Patch Management**: Generate and test patches using AI (OpenHands)
- **Docker Integration**: Build, test, and push Docker images
- **Comprehensive Output**: JSON-formatted results with detailed test metrics

---

## Prerequisites

### Environment Setup
1. **Configure environment variables**:
```bash
export GITHUB_ACCESS_TOKEN=your_github_token
export LLM_API_KEY=your_api_key # if using LLM filtering
export DOCKER_HUB_USER=your_username # optional, for pushing images
export DOCKER_HUB_REPO=repository # optional, for pushing images
```

2. **Install Python dependencies**:
```bash
pip install cmakeast docker pygithub jsonschema openai numpy scipy
```

3. **Build Docker images** for different C++ versions:
```bash
docker build -t cpp20 -f docker/Dockerfile.20.04 .
docker build -t cpp22 -f docker/Dockerfile.22.04 .
docker build -t cpp24 -f docker/Dockerfile.24.04 .
```
Note: Prebuilt Docker images are available on DockerHub[https://hub.docker.com/repository/docker/tommyho1999/opt-repo-cpp]

4. **Install OpenHands** (optional):
```bash
docker pull docker.openhands.dev/openhands/openhands:1.3

# openhands runtime image (can use different ones, defined in src/config/settings.py)
docker pull ghcr.io/openhands/runtime:oh_v1.3.0_odjrubqcfxjb4y1s_kxyxnblfp0d1rp6p
```
Note: OpenHands commit patches can be found in ```data/patches/``` as ```*.patch``` files.

---

## Project Structure
├── main.py                  # Main entry point
├── src/                     # Source code
│   ├── core/                # Core functionality
│   └── config/              # Configuration handling
├── data/                    # Output directory
│   ├── collect.txt          # Collected repositories
│   ├── testcollect.txt      # Validated repositories
│   ├── fail.txt             # Failed repositories
│   ├── filtered_commits.txt # Filtered commits
│   └── commits/             # Individual commit test results
└── docker/                  # Docker configuration files

# Running
1. **Collecting Repositories**
Use the --collect flag to crawl GitHub for C++ repositories:
```bash
# Basic collection (default: 10 repos, min 20 stars, max 1000 stars)
python3 main.py --collect

# Collect 50 repositories
python3 main.py --collect --limit=50

# Collect repositories with up to 5000 stars
python3 main.py --collect --stars=5000

# Collect and immediately test repositories
python3 main.py --collect --test
```

**Outputs**
- ```data/collect.txt``` - Raw collection results (owner/repo per line)
- ```data/testcollect.txt``` - Successfully validated (structure, build and test) repositories
- ```data/fail.txt``` - Repositories that failed validation

2. **Testing Collected Repositories**
If you collected repositories without the --test flag, validate them later:
```bash
python3 main.py --testcollect --input=data/collect.txt
```

3. **Analyzing Commits**
Filter commits from collected repositories:
```bash
# Basic commit collection with LLM filtering
python3 main.py --commits --filter=llm --input=data/collect.txt

# Collect and immediately test commits
python3 main.py --commits --test --filter=llm --input=data/collect.txt
```

**Output**:
- ```data/filtered_commits.txt``` per line ```owner/repo | newsha | oldsha```

4. **Testing Commits**
Test previously collected commits:
```bash
python3 main.py --testcommits --input=data/filtered_commits.txt
```

**Output**:
- JSON files in ```data/commits/owner_repo_newsha.json``` containing:
    - Build and test commands executed
    - Execution times
    - Statistical analysis
    - Pass/fail status

5. **Docker Operations**
```bash
# Test from a folder of JSON results
python3 main.py --testdocker --input=data/commits/

# Test from a filtered commits file
python3 main.py --testdocker --input=data/filtered_commits.txt

# Test a specific Docker image
python3 main.py --testdocker --docker=owner_repo_newsha
```

**Generate Docker Images** (no testing):
```bash
python3 main.py --genimages --input=data/commits/
```

**Push Images to Dockerhub**:
```bash
python3 main.py --pushimages --input=data/commits/
```

6. **Patch Management**:
Generate and test patches using OpenHands:
```bash
# Generate a patch for a specific commit
python3 main.py --patch --repo=owner/repo --sha=<commit_sha> --prompt="Fix memory leak"

# Test a patch from a mounted folder
python3 main.py --testpatch --docker=owner_repo_newsha --mount=/path/to/patched/folder

# Test a patch from a diff file (the diff file is applied to /test_workspace/workspace/old)
python3 main.py --testpatch --docker=owner_repo_newsha --diff=/path/to/diff.patch
```

---

## Docker Container Structure

When running tests in Docker, the container has the following structure:
- ```/test_workspace/workspace/old``` - Original commit
- ```/test_workspace/workspace/new``` - Patched commit
- ```/test_workspace/old_build.sh```  - Original build script
- ```/test_workspace/new_build.sh```  - Patched build script
- ```/test_workspace/old_test.sh```   - Original test script
- ```/test_workspace/new_test.sh```   - Patched test script

---

## Example
Testing docker images:
```bash
docker pull tommyho1999/opt-repo-cpp:owner_repo_newsha
docker tag tommyho1999/opt-repo-cpp:owner_repo_newsha owner_repo_newsha
python3 main.py --testdocker --docker=owner_repo_newsha
```

