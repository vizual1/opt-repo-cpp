import logging
from src.config import test_flags_filter

class FlagFilter:
    def __init__(self, testing_flags: dict[str, dict[str, str]]):
        self.testing_flags = testing_flags
        self.valid_flags: set[str] = set()

    def get_valid_flags(self) -> list[str]:
        all_flags = set(self.testing_flags.keys())
        valid = all_flags & set(test_flags_filter.get("valid", []))
        prefix = {f for f in all_flags if any(f.startswith(p) for p in test_flags_filter.get("prefix", []))}
        suffix = {f for f in all_flags if any(f.endswith(p) for p in test_flags_filter.get("suffix", []))}
        contains = {f for f in all_flags if any(sub in f for sub in test_flags_filter.get("in", []))}
        self.valid_flags = valid | prefix | suffix | contains

        logging.debug(f"FlagFilter: Found {len(self.valid_flags)} valid flags: {sorted(self.valid_flags)}")
        return list(self.valid_flags)