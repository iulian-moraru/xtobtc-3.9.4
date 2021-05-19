import os
import logging
from datetime import datetime


def ensure_dir(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)


def initlog(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    now = datetime.utcnow()
    date_time = now.strftime("%Y_%m_%d")
    logfile = f"logs/{name}-{date_time}.log"
    ensure_dir(logfile)
    my_fh = logging.FileHandler(logfile, delay=True)
    my_fh.setLevel(logging.INFO)
    formatter_file = logging.Formatter(
        '%(asctime)s %(levelname) -10s %(name) -10s %(funcName) -10s %(lineno) -5d  %(message)s'
    )
    my_fh.setFormatter(formatter_file)
    logger.addHandler(my_fh)

    my_ch = logging.StreamHandler()
    my_ch.setLevel(logging.INFO)
    # create formatter and add it to the handlers
    formatter_console = logging.Formatter(
        '%(asctime)s %(levelname) -10s %(name) -10s %(lineno) -5d  %(message)s'
    )
    my_ch.setFormatter(formatter_console)
    # add the handlers to logger
    logger.addHandler(my_ch)
    return logger
