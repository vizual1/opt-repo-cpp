import logging, sys, signal
from src.input import start
from src.utils.logging import logging_setup

CHILD_PROCESSES = []

def register_child_process(p):
    CHILD_PROCESSES.append(p)

def sigint_handler(sig, frame):
    logging.warning("SIGINT received. Cleaning up child processes...")
    for p in CHILD_PROCESSES:
        try:
            p.terminate()
        except Exception:
            pass
    sys.exit(1)


def main() -> None:
    logging.info("Starting the GitHub repository pipeline...")
    start()
    logging.info("Pipeline finished successfully.")

if __name__ == '__main__':
    try:
        logging_setup()
        signal.signal(signal.SIGINT, sigint_handler)
        main()

    except KeyboardInterrupt:
        # fallback if signal handler misses it
        logging.warning("Interrupted by user")
        sigint_handler(None, None)