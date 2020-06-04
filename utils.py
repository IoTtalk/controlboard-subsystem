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


def bigger(data, threshold, avg):
    """
    Check if data > threshold. Return comparison results as boolean, string.

    Args:
        data: data pulled from IoTTalk server.
        threshold: threshold settings from rule_info in memory.
        avg: the average of history data stored in memory.

    Returns:
        triggered: whether the rule is satisfied by arg data
        color: Card color in UI.
    """
    if data > threshold:
        triggered = True
        color = 'green'
    else:
        triggered = False
        print('bigger', 0.5 * (threshold - avg) + avg)
        if data > 0.5 * (threshold - avg) + avg:
            color = 'yellow'
        else:
            color = 'unchanged'

    return triggered, color


def smaller(data, threshold, avg):
    """Check if data < threshold. Return comparison results as boolean, string.

    Args:
        data: data pulled from IoTTalk server.
        threshold: threshold settings from rule_info in memory.
        avg: the average of history data stored in memory.

    Returns:
        triggered: whether the rule is satisfied by arg data
        color: Card color in UI.
    """
    if data < threshold:
        triggered = True
        color = 'green'
    else:
        triggered = False
        print('smaller', 0.22 * (avg - threshold) + threshold)
        if data < 0.22 * (avg - threshold) + threshold:
            print(data, 'yellow')
            color = 'yellow'
        else:
            color = 'unchanged'
    return triggered, color


def bigger_equal(data, threshold, avg):
    """Check if data >= threshold. Return comparison results as boolean, string.

    Args:
        data: data pulled from IoTTalk server.
        threshold: threshold settings from rule_info in memory.
        avg: the average of history data stored in memory.

    Returns:
        triggered: whether the rule is satisfied by arg data
        color: Card color in UI.
    """
    if data >= threshold:
        triggered = True
        color = 'green'
    else:
        print('biggerequal', 0.78 * (threshold - avg) + avg)
        triggered = False
        if data > 0.78 * (threshold - avg) + avg:
            color = 'yellow'
        else:
            color = 'unchanged'

    return triggered, color


def smaller_equal(data, threshold, avg):
    """Check if data <= threshold. Return comparison results as boolean, string.

    Args:
        data: data pulled from IoTTalk server.
        threshold: threshold settings from rule_info in memory.
        avg: the average of history data stored in memory.

    Returns:
        triggered: whether the rule is satisfied by arg data
        color: Card color in UI.
    """
    if data <= threshold:
        triggered = True
        color = 'green'
    else:
        triggered = False
        print('smallerequal', 0.22 * (avg - threshold) + threshold)
        if data < 0.22 * (avg - threshold) + threshold:
            color = 'yellow'
        else:
            color = 'unchanged'
    return triggered, color


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



condition_handler = {
    'bigger': bigger,
    'smaller': smaller,
    'biggerandequal': bigger_equal,
    'smallerandequal': smaller_equal
}
