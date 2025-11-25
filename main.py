import logging
from src.input import start
from src.utils.logging import logging_setup

def main() -> None:
    logging.info("Starting the GitHub repository pipeline...")
    start()
    logging.info("Pipeline finished successfully.")

if __name__ == '__main__':
    logging_setup()
    main()