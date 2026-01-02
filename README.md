# Build
1.  ```bash
    docker build -t cpptool .
    docker build --progress=plain -t cpptool .
2.  ```bash
    docker run -it -v "%cd%":/app cpptool
    docker run -it -v ${PWD}:/app cpptool
    ```

docker build -t cpp18 -f docker/Dockerfile.18.04 .
docker build -t cpp20 -f docker/Dockerfile.20.04 .
docker build -t cpp22 -f docker/Dockerfile.22.04 .
docker build -t cpp24 -f docker/Dockerfile.24.04 .

pip install cmakeast docker pygithub jsonschema openai numpy scipy

0. --popular should crawl github and find all repos according to some condition/filter and save it into a .txt file. Example:
```python3 main.py --popular -stars=1000 -limit=10 -output="data/crawl.txt"```
1. --testcrawl should read in some file that saves repositories in a list of the form of owner/repo, or take a reponame of the form owner/repo. Example:
```python3 main.py --testcrawl -input="data/crawl.txt" -output="data/test.txt"```
```python3 main.py --testcrawl -repo="owner/repo" -output="data/test.txt"```
Additionally, --testcrawl can take a -docker name to run the test with the given docker. Example
```python3 main.py --testcrawl -repo="owner/repo" -output="data/test.txt" -docker=<docker_image_name>```
2. --commits should take the main branch of a github repo and gather and filter commits according to some condition/filter and save it into a .txt file in the form of ```new_sha | old_sha```, or it can take a file with repos from (1). The type of filter can be defined with -filter. For using LLMs, we can define them in src/config.py. Example:
```python3 main.py --commits -repo="owner/repo"```
```python3 main.py --commits -input="data/test.txt" -filter="llm"```
3. --testcommits can take an -input (of all filtered commits) from (2), -repo if there is a file under config.py under 'data/commits' with name 'owner_repo_filtered.txt' saved as in (2). Additionally, a pair of newsha and oldsha for comparison (can be a commit and its parent), or a SHA value can also be used to test commits. Example:
```python3 main.py --testcommits -input="path/to/owner_repo_filtered.txt"```
```python3 main.py --testcommits -repo="owner/repo"```
```python3 main.py --testcommits -newsha="<new_sha>" -oldsha="<old_sha>"```
```python3 main.py --testcommits -sha="<sha>"```
Additionally, --testcommits can take a -docker name to run the test with the given docker.
4. --test can take as an input an entire folder of .tar docker images output from (3) and run the test for each of them, or can take a single .tar docker image file or a docker image name as in (1) or (3) to test a single docker image. Additionally, one can define a mount directory that will automatically run the test of the old commit and the mounted project and evaluate the performance improvment. Example:
```python3 main.py --test -input="<folder_with_docker_tar_files>"```
```python3 main.py --test -docker=<docker_tar_file_or_image_name>```
```python3 main.py --test -mount=<dir> -docker=<docker_tar_file_or_image_name>```


