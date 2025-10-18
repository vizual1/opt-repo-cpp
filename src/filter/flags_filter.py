from src.config import test_flags_filter

class FlagFilter:
    def __init__(self, testing_flags: dict[str, dict[str, str]]):
        self.testing_flags = testing_flags
        self.valid_flags: list[str] = []

    def get_valid_flags(self) -> list[str]:
        self.valid_flags = list(set(test_flags_filter["valid"]) & self.testing_flags.keys())
        self.valid_flags += [y for y in self.testing_flags if any(y.startswith(x) for x in test_flags_filter["prefix"])]
        self.valid_flags += [y for y in self.testing_flags if any(y.endswith(x) for x in test_flags_filter["suffix"])]
        self.valid_flags += [y for y in self.testing_flags if any(x in y for x in test_flags_filter["in"])]
        return self.valid_flags