import logging

# TODO: better package conflict resolve
def check_package_conflict(parent_packages: set[str], current_packages: set[str]):
    logging.info("Checking for package conflicts...")
    if parent_packages == current_packages:
        return False

    if parent_packages.issubset(current_packages) or current_packages.issubset(parent_packages):
        return False
    
    return True # possible conflict

# TODO: flags conflict resolve
# TODO: maybe even need some of form of SMT solver (AND, OR, NOT, etc.)
# TODO: find solution to reach => maybe overkill
def check_flag_conflict():
    return False 