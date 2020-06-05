import configparser
import logging
import os
import sys


config_path = str(sys.argv[1])

config = configparser.ConfigParser()
config.read(config_path)

log_root = config['env']['logroot']
if not os.path.isdir(log_root):
    os.makedirs(log_root)


def make_logger(log_name, log_file):
    '''
    Inits a Logger with title log_name and file name that stores informations from this logger

    Args:
        log_name: Title of this logger, used in presentation of log streaming.
        log_file: File name to store logs from this logger.

    Returns:
        A logger object with fixed logging format.
    '''
    logger = logging.getLogger(f'[{log_name}]')
    logger.setLevel(logging.INFO)

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)

    log_file_path = os.path.join(log_root, log_file + '.log')
    fh = logging.FileHandler(log_file_path)
    fh.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    sh.setFormatter(formatter)
    fh.setFormatter(formatter)

    logger.addHandler(sh)
    logger.addHandler(fh)

    return logger


def connect_db(logger, cb_db):
    '''
    Create a connection to MySQL Database specified in config

    Args:
        config: Config object read from user specified .ini file.
        logger: Logger object to write log in.
        cb_db: Database object to be bind. 

    Returns:
        cb_db: MySQL Database Connection
    '''
    cb_db.bind(
        provider='mysql',
        host=config['db']['host'],
        user=config['db']['user'],
        passwd=config['db']['pwd'],
        db=config['db']['dbname']
    )
    cb_db.generate_mapping(create_tables=True)

    logger.info('\tConnecting to Database\t......done')

    return
