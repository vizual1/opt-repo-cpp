import subprocess, os, logging

def run_openhands_patching(workspace_base_path: str):
    """
    workspace_base_path: The local path where your .tar image is extracted/mounted.
    It should contain /workspace/old and /logs/results.json
    """
    
    # Define the precise instructions for the Agent
    task_instruction = (
        "1. Examine the performance metadata in '/test_workspace/logs/results.json'.\n"
        "2. Create a new directory at '/test_workspace/workspace/patched' by copying everything from '/test_workspace/workspace/old'.\n"
        "3. Based on the performance bottlenecks or suggestions identified in results.json, "
        "modify the code in '/test_workspace/workspace/patched' to implement those improvements.\n"
        "4. Ensure the patched code remains functionally correct while applying the performance logic found in the logs."
    )

    # Environment variables to point OpenHands to your Ollama instance
    env = os.environ.copy()
    env["LLM_MODEL"] = "ollama/your-model" # e.g., llama3
    env["LLM_BASE_URL"] = "http://localhost:11434"

    command = [
        "python", "-m", "openhands.core.main",
        "-t", task_instruction,
        "-d", workspace_base_path, # This mounts your extracted .tar structure as the workspace
        "--sandbox-container-image", "python:3.11-slim" # Or your specific image
    ]

    logging.info("Starting OpenHands patching agent...")
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    return result.stdout

import json
from openhands.sdk import LLM, Conversation
from openhands.tools.preset.default import get_default_agent

class CodePatcher:
    def __init__(self, workspace_path, custom_image="my-project-env:latest"):
        self.workspace_path = workspace_path
        # Configure LLM to point to your local Ollama instance
        self.llm = LLM(
            model="ollama/qwen2.5:7b", # Change to your model (e.g., codellama, qwen2.5-coder)
            base_url="http://host.docker.internal:11434/v1", 
            api_key="ollama"
        )
        self.custom_image = custom_image

    def patch_from_json(self, json_file):
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Extract the error or instruction from your results.json
        issue_description = data.get("issue", "Fix the bugs in this directory.")
        
        # Initialize the agent
        agent = get_default_agent(llm=self.llm)
        
        # Start a conversation in the specified workspace
        # We tell it to use the custom Docker image we loaded earlier
        conversation = Conversation(
            agent=agent, 
            workspace=self.workspace_path,
            runtime_container_image=self.custom_image 
        )
        
        # Tell the agent what to do based on the JSON
        conversation.send_message(f"Please fix the following issue: {issue_description}")
        
        # Run the agent until the task is complete
        conversation.run()

# Usage
patcher = CodePatcher(workspace_path="./my_project_code")
patcher.patch_from_json("results.json")