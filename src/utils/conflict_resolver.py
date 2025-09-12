import logging

def check_package_conflict(parent_packages: set[str], current_packages: set[str]):
    logging.info("Checking for package conflicts...")
    if parent_packages == current_packages:
        return False

    if parent_packages.issubset(current_packages) or current_packages.issubset(parent_packages):
        return False
    
    return True # possible conflict