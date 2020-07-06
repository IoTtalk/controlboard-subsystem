import configparser
import logging
import os
import sys


from pony import orm


from models import UserRule, CB_Account, CB_SA


running_sa = dict() # used to record AG SA. in format {sa_id: AG SA token}
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
    retry_times = 0
    cb_db.bind(
        provider='mysql',
        host=config['db']['host'],
        user=config['db']['user'],
        passwd=config['db']['pwd'],
        db=config['db']['dbname'],
        port=int(config['db']['port'])
    )
    cb_db.generate_mapping(check_tables=False)
    while (retry_times < 3):
        try:
            cb_db.create_tables()
            logger.info('\tConnecting to Database\t......done')
            break
        except orm.dbapiprovider.InternalError:
            logger.error('\t\tInternal Error Encountered, try remove tables and reconnect...')
            cb_db.drop_all_tables(with_all_data=True)
            cb_db.disconnect()
            retry_times += 1

    return


@orm.db_session
def test_db(logger):
    '''
    Write dummy data to database for testing connection.

    Args:
        logger: Logger object to write log in.

    Returns: None
    '''
    try:
        test_account = CB_Account(
            account='test',
            privilige='1',
        )

        test_sa = CB_SA(
            cb_name='test_sa',
            account_set=test_account
        )

        test_rule = UserRule(
            rule_type='Sensor',
            actuator_alias='test_actuator',
            sa=test_sa
        )

        test_account.sa_set.add(test_sa)
        test_sa.rule_set.add(test_rule)

        logger.info('\tTest database connection \t......done')
    except Exception as err:
        logger.error(err)

    return
