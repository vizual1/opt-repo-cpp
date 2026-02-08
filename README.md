# Preparation
1. Ensure access_key, api_key, etc. set
2. pip install cmakeast docker pygithub jsonschema openai numpy scipy
3.  ```bash
    docker build -t cpp20 -f docker/Dockerfile.20.04 .
    docker build -t cpp22 -f docker/Dockerfile.22.04 .
    docker build -t cpp24 -f docker/Dockerfile.24.04 .
4. Docker images found under https://hub.docker.com/repository/docker/tommyho1999/opt-repo-cpp

# Running
1. ```collect``` flag crawls github and collects C++ repositories. The output can be found under ```data/collect.txt```, where the repositories are saved as ```owner/repo``` per line:
```bash
python3 main.py --collect
python3 main.py --collect --limit=10 //sets the amount of repositories to collect
python3 main.py --collect --stars=1000 //sets the maximum amount of stars (minimum is 20) of a collected repository
```
An additional ```test``` flag allows the found C++ repositories to be further filtered according to structural requirements, buildability and testability of the most recent commit of the repository. The output can be found under ```data/testcollect.txt``` for success and ```data/fail.txt``` for failure.
```bash
python3 main.py --collect --test
```
If no ```test``` flag was set with the ```collect``` flag, and the user wants to further filter according to structural requirements, buildability and testability. Then rerun with the ```testcollect``` flag with the collected repositories as input:
```bash
python3 main.py --testcollect --input=data/collect.txt
```
The output can be found under ```data/testcollect.txt``` for success and ```data/fail.txt``` for failure.


2. ```commits``` flag takes in a file of repositories of the form ```owner/repo``` per line. It collects the commits of each repository and filters it with the LLM according to the set filter, and saves it to output ```data/filtered_commits.txt``` (each line has the from ```owner/repo | patched_SHA | original_SHA```)
```bash
python3 main.py --commits --filter=llm --input=data/collect.txt
```
An additional ```test``` flag allows the collected commits to be directly build and tested, gathering test results (commands run, test times, statistical analysis).
If no ```test``` flag was set with ```commits``` flag. Then 
```bash
python3 main.py --testcommits --input=data/filtered_commits.txt
```
can be run to test all the collected commits. The ```test``` or ```testcommits``` output will be at ```data/commits/```, where each file ```owner_repo_newsha.json``` (newsha is the SHA hash of the new (patched) commit) is saved with the results of the ```old``` (original) and ```new``` (patched) test runs (commands run, test times, statistical analysis).

3. ```testdocker``` flag takes in a file, where each line is of the form ```owner/repo | patched_SHA | original_SHA```, a folder, where each file in the folder is of the form ```owner_repo_newsha.json```, or a docker image of the form ```owner_repo_newsha```. If the input is a folder or file ensure that the docker images exist with the name ```owner_repo_newsha``` for each. A container of the image will be generated, built and tested.
```bash
python3 main.py --testdocker --input=data/commits/
python3 main.py --testdocker --input=data/filtered_commits.txt
python3 main.py --testdocker --docker=<docker_image>
```
The output will be at ```data/commits/```, where each file ```owner_repo_newsha.json``` (newsha is the SHA hash of the new (patched) commit) is saved with the results of the ```old``` (original) and ```new``` (patched) test runs (commands run, test times, statistical analysis). 

4. ```testpatch``` takes in a docker image (name should be ```owner_repo_newsha```) and a mount path to the folder of the patched code, or a diff file (generated with ```git diff```) that will be applied to the ```old``` (original) commit.
```bash
python3 main.py --testpatch --docker=<docker_image> --mount=/path/to/patched/folder
python3 main.py --testpatch --docker=<docker_image> --diff=/path/to/diff/file
```
The output will be at ```data/commits/```, where each file ```owner_repo_newsha.json``` (newsha is the SHA hash of the new (patched) commit) is saved with the results of the ```old``` (original) and ```new``` (patched) test runs (commands run, test times, statistical analysis). 


# Other Flags
1. ```genimages```
2. ```pushimages```
3. ```patch```


