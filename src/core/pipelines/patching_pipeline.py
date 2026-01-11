import logging, subprocess, requests
from src.config.config import Config

#from openhands.sdk import LLM, Conversation, Agent
#from openhands.tools.preset.default import get_default_agent, get_default_tools

class PatchingPipeline():
    def __init__(self, config: Config):
        url = "http://localhost:3000/api/conversations"

        payload = {
            "system_prompt": (
                "You are OpenHands.\n"
                "You have access to /workspace/old (read-only) and /workspace/patched (writeable).\n"
                "Your task is to generate and apply a performance patch based on the commit message."
            ),
            "user_prompt": (
                "Commit message: \"Use _mm512_reduce_add_ps and _mm512_reduce_add_pd instead of custom sequences\".\n"
                "Affected file: include/xsimd/arch/xsimd_avx512f.hpp.\n"
                "Start now."
            )
        }

        response = requests.post(url, json=payload)
        print(response.json())
        self.config = config
    """
    def patch_all(self) -> None:
        with open(self.config.input_file, 'r', errors='ignore') as f:
            lines = f.readlines()
        
        for line in lines:
            image = line.strip()

            self.extract_workspace(image)


    def patch(self, commit) -> None:
        llm = LLM(
            provider="openai",
            model="gpt-5-mini",
            api_key="YOUR_KEY"
        )

        agent = Agent(
            llm=llm,
            tools=get_default_tools(),
            system_prompt_filename='system_prompt.j2' 
        )

        logging.info("Agent initialized. Sending task...")
        conversation = Conversation(agent=agent, workspace="./my_code")
        conversation.agent.init_state(conversation._state, on_event=self._on_event)

        conversation.send_message(self._user(None))

        conversation.run()
    """
    def _system(self) -> str:
        return """
        You are OpenHands, an autonomous software engineering agent.

        Your task is to generate a performance-improving patch based on the
        provided commit intent and filesystem state.

        Rules:
        - You may execute shell commands.
        - You may inspect files.
        - You must generate a unified diff patch.
        - The patch must apply cleanly with `patch -p1`.
        - Do NOT modify /workspace/workspace/old directly.
        - Create /workspace/workspace/patched instead.
        - Validate that patched reflects the intent of the commit message.
        - Restrict changes to the listed affected files.
        - Output the final patch to /workspace/workspace/patch/old_to_new.patch.

        You must work step-by-step using tools.
        """
    
    def _user(self, commit) -> str:
        return f"""
        Generate a performance-improving patch.

        Context:
        - Commit message: "{commit.message}"
        - Affected files: include/xsimd/arch/xsimd_avx512f.hpp
        - Expected change: small refactor, fewer instructions, better SIMD intrinsic usage
        - Old code: /workspace/workspace/old
        - New code: /workspace/workspace/new

        Instructions:
        1. Inspect the old code.
        2. Apply changes implied by the commit message.
        3. Generate a unified diff patch.
        4. Apply it to a copy of old -> /workspace/workspace/patched.
        5. Validate correctness.
        6. Save patch to /workspace/workspace/patch/old_to_new.patch.
        """
    
    def extract_workspace(self, image_name, out_dir="/test_workspace"):
        container_name = "temp_extract_container"

        subprocess.run(["docker", "create", "--name", container_name, image_name], check=True)
        subprocess.run(["docker", "cp", f"{container_name}:/test_workspace", out_dir], check=True)
        subprocess.run(["docker", "rm", container_name], check=True)

    def _on_event(self, event):
        if hasattr(event, 'message'):
            logging.info(f"\n[AGENT]: {event.message}")
        if hasattr(event, 'action'):
            logging.info(f"\n[ACTION]: {event.action}")