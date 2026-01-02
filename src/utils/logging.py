import logging, sys
from datetime import datetime
from pathlib import Path

def logging_setup() -> None:
    LOG_DIR = Path("logs")
    LOG_DIR.mkdir(exist_ok=True)

    log_filename = LOG_DIR / f"logging_{datetime.now():%Y-%m-%d-%H-%M}.log"

    logging.basicConfig(
        filename=log_filename,
        filemode='a',
        format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
        datefmt='%H:%M:%S',
        level=logging.INFO
    )

    logging.info(f"Command run: {' '.join(sys.argv)}")