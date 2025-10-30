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
```python3 main.py --popular -stars=1000 -limit=10```
1. --testcrawl should read in some file that saves repositories in a list of the form of https://github.com/owner/repo. Example:
```python3 main.py --testcrawl -input="data/crawl.txt"```
2. --commits should take the main branch of a github repo and gather and filter commits according to some condition/filter and save it into a .txt file in the form of ```new_sha | old_sha | commit_msg | issue as #NUMBER```. Example:
```python3 main.py --commits -repo="<url>"```
3. --testcommits should take an input (of all filtered commits) from point 2, the repo if there is a file under config.py in 'commits' with name commits/owner_reponame.txt saved as in point 2, a pair of newsha and oldsha for comparison (can be a commit and its parent), or a SHA value. Example:
```python3 main.py --testcommits -input="<name>.txt"```
```python3 main.py --testcommits -repo="<url>"```
```python3 main.py --testcommits -newsha="<new_sha>" -oldsha="<old_sha>"```
```python3 main.py --testcommits -sha="<sha>"```

