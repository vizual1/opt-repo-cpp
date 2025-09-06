import os

storage: dict[str, str] = {
    "dataset": "data",
    "repo_urls": "data/repo_urls.txt",
    "history": "history.txt",
    "filtered": "filtered.txt",
    "results": "results.txt"
}

github: dict[str, str] = {
    'access_token': os.environ['access_token']
}

likelihood: dict[str, int] = {
    'min_likelihood': 50,
    'max_likelihood': 50
}