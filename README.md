# C++ Performance Optimization Commit Dataset Pipeline

This repository contains the automated pipeline used in the thesis:

"Automated Construction of a Dataset of Performance-Improving Commits from Open-Source C++ Projects"

The pipeline collects repositories from GitHub, identifies candidate performance-improving commits, builds and executes them in Docker environments, and performs statistical performance evaluation.

## Overview

The pipeline performs the following steps:

1. Repository collection from GitHub
2. Structural commit filtering
3. LLM-based classification of candidate performance-improving commits
4. Containerized build and test execution
5. Statistical runtime analysis
6. Dataset generation

The resulting dataset contains executable commits and Docker environments that enable reproducible performance measurements.

## Artifacts

Dataset and Docker images:

DockerHub  
https://hub.docker.com/repository/docker/tommyho1999/opt-repo-cpp

## Features

- Automated repository collection from GitHub
- LLM-based commit classification
- Docker-based reproducible execution environments
- Automated dependency resolution
- Statistical performance evaluation
- Integration with OpenHands for patch generation experiments

---

## Prerequisites

### Environment Setup
1. **Configure environment variables**:
```bash
export GITHUB_ACCESS_TOKEN=your_github_token
export LLM_API_KEY=your_api_key # if using LLM filtering
export DOCKER_HUB_USER=your_username # optional, for pushing or pulling images
export DOCKER_HUB_REPO=repository # optional, for pushing or pulling images
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
```
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
```

# Running
1. **Collecting Repositories**
Use the --collect flag to crawl GitHub for C++ repositories:
```bash
# Collect and structurally validate (most recent commit): 
# 10 repos (min 20 stars, max 1000 stars)
python3 main.py --collect --repos=10 --stars=1000

# Collect, structurally validate, and build and test (most recent commit)
python3 main.py --collect --repos=10 --stars=1000 --test

# Structurally validate, and build and test (most recent commit)
python3 main.py --testcollect --input=data/collect.txt
```

**Outputs**
- ```data/collect.txt``` - Raw collection results (owner/repo per line)
- ```data/testcollect.txt``` - Successfully validated structure, or with ```--test``` build and test, repositories (owner/repo per line)
- ```data/fail.txt``` - Repositories that failed validation (owner/repo per line)

2. **Collecting Commits**
Filter commits from collected repositories:
```bash
# Collect and filter commits with LLM
python3 main.py --commits --filter=llm --input=data/collect.txt

# Collect and filter commits, then build and test commits
python3 main.py --commits --test --filter=llm --input=data/collect.txt

# Build and test commits
python3 main.py --testcommits --input=data/filtered_commits.txt
```

**Output**:
- ```data/filtered_commits.txt``` - filtered commits (```owner/repo | newsha | oldsha``` per line)
- ```data/commits/owner_repo_newsha.json``` - multiple JSON files of built and tests commits, containing:
    - Build and test commands executed
    - Execution times
    - Statistical analysis

3. **Docker Operations**
```bash
# Test from a filtered commits file
python3 main.py --testdocker --input=data/filtered_commits.txt

# Test from a folder of JSON files of collected commits
python3 main.py --testdocker --input=data/dataset/

# Test a specific Docker image
python3 main.py --testdocker --docker=owner_repo_newsha

# Generate Docker images without testing of collected commits from a folder of JSON files
python3 main.py --genimages --input=data/dataset/

# Pulls Docker images from Dockerhub of collected commits from a folder of JSON files
python3 main.py --pullimages --input=data/dataset/
```

4. **Patch Management**:
Generate and test patches using OpenHands:
```bash
# Generate a patch for a specific commit
python3 main.py --patch --repo=owner/repo --sha=<commit_sha> --prompt="Fix memory leak"

# Test a patch from a mounted folder
python3 main.py --testpatch --docker=owner_repo_newsha --mount=/path/to/patched/folder

# Test a patch from a diff file (the diff file is applied to /test_workspace/workspace/old)
python3 main.py --testpatch --docker=owner_repo_newsha --diff=/path/to/diff.patch
```
**Output**:
- ```data/patch/``` - patch files generated by ```--patch``` flag.
- ```data/commits/owner_repo_newsha.json``` - multiple JSON files of built and tests of generated patches, containing:
    - Build and test commands executed
    - Execution times
    - Statistical analysis

---

## Docker Container Structure
When running tests in Docker, the container has the following structure:
- ```/test_workspace/workspace/old``` - Original commit
- ```/test_workspace/workspace/new``` - Patched commit
- ```/test_workspace/old_build.sh```  - Original build script
- ```/test_workspace/new_build.sh```  - Patched build script
- ```/test_workspace/old_test.sh```   - Original test script
- ```/test_workspace/new_test.sh```   - Patched test script
