import configparser
import datetime
import logging
import os
import sys
import time


from flask import Flask
from flask import jsonify
from flask import request
from flask import render_template


from eventhandler import apis


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


def recover_sa(config, logger):
    '''
    Recover SAs stored in Database.

    Args:
        config: Config object read from user specified .ini file.
        logger: Logger object to write log in.

    Returns:
        None
    '''
    config_path = str(sys.argv[1])

    config = configparser.ConfigParser()
    config.read(config_path)

    print(config['IoTtalk']['serverip'])


if __name__ == "__main__":
    config_path = str(sys.argv[1])

    config = configparser.ConfigParser()
    config.read(config_path)

    log_root = config['local']['logroot']
    if not os.path.isdir(log_root):
        os.makedirs(log_root)
    
    system_logger = make_logger('System', 'system')
    system_logger.info('Start Launching ControlBoard Subsystem......')

    app = Flask(__name__)
    system_logger.info('Create Server......done')

    app.register_blueprint(apis)
    system_logger.info('Create EventHandler......done')



    app.run(
        host=config['env']['host'],
        port=config['env']['port'],
        threaded=True
    )
