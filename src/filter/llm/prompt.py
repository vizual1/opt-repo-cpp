class Prompt():
    class Message():
        def __init__(self, role: str, content: str):
            self.role = role
            self.content = content

    def __init__(self, messages: list[Message]):
        self.messages = messages

