import logging, subprocess

def find_apt_package(cdep_name: str) -> str:
    """Find corresponding apt package dynamically from CMake dependency name."""
    try:
        logging.info(f"Trying to find_apt_package: {cdep_name}")
        result = subprocess.run(['apt-cache', 'search', cdep_name],
                                capture_output=True, text=True, check=False)
        lines = result.stdout.splitlines()
        dev_packages = [line.split(' - ')[0] for line in lines if 'dev' in line]
        if dev_packages:
            logging.info(f"Found dev_packages for {cdep_name}: {dev_packages[0]}")
            return dev_packages[0]
    except FileNotFoundError:
        logging.error(f"No dev_packages for {cdep_name} found.")
        pass

    return ''