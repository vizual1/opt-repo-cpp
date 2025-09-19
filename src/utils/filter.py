import re, logging
from github.Commit import Commit
import src.config as conf
from src.llm.prompt import Prompt
from src.llm.openai import OpenRouterLLM

def simple_filter(commit: Commit) -> bool:
    msg = commit.commit.message
    if "optimi" in msg:
        return True
    elif "improv" in msg:
        return True
    return False

def llm_filter(llm: OpenRouterLLM, repo_name: str, commit: Commit) -> bool:
    p = Prompt([Prompt.Message("user",
                                f"The following is the message of a commit in the {repo_name} repository:\n\n###Message Start###{commit.commit.message}\n###Message End###"
                                + f"\n\nHow likely is it for this commit to be a performance improving commit in terms of execution time? Answer by only writing the likelihood in the following format:\nLikelihood: x%"
                                )])
    res = llm.generate(p)

    match = re.search(r"Likelihood:\s*([0-9]+(?:\.[0-9]+)?)%", res)
    if match:
        likelihood = float(match.group(1))
    else:
        logging.info(f"Commit {commit.sha} in {repo_name} did not return a valid likelihood response.")
        return False

    if likelihood < conf.likelihood['min_likelihood']:
        logging.info(f"Commit {commit.sha} in {repo_name} has a likelihood of {likelihood}%, which is below the threshold.")
        return False
    if likelihood >= conf.likelihood['max_likelihood']:
        logging.info(f"Commit {commit.sha} in {repo_name} has a high likelihood of being a performance commit ({likelihood}%).")
        return True

    """
    diff = self.get_diff(commit)

    # Second stage, ask O4
    p = Prompt([Prompt.Message("user",
                                f"The following is the message of a commit in the {repo.full_name} repository:\n\n###Message Start###{commit.commit.message}\n###Message End###"
                                + f"\n\nThe diff of the commit is:\n\n###Diff Start###{diff}\n###Diff End###"
                                + f"\n\nIs this commit a performance improving commit in terms of execution time? Answer with 'YES' or 'NO'."
                                )])

    tokens_cnt = len(tiktoken.encoding_for_model("o3").encode(p.messages[0].content))

    if tokens_cnt > conf.llm['max-o4-tokens']:
        logging.info(f"Commit {commit.sha} in {repo.full_name} has too many tokens ({tokens_cnt}), skipping.")
        return False

    res = self.o4.get_response(p)
    """
    return 'YES' in res and 'NO' not in res

# TODO: add other filters, CMakeLists.txt is at root
# TODO: enable_testing() and add_test() in CMakeLists.txt
# TODO: filter commits by changes to cpp code


 