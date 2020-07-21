import logging
import requests
import os
import uuid


from pony import orm


from config import env_config, reg_config
from models import UserRule, CB_Account, CB_SA


'''
used to record AG SA. in format {sa_id: CB_SA entity}
'''
running_sa = dict() 


log_root = env_config['env']['logroot']
if not os.path.isdir(log_root):
    os.makedirs(log_root)

default_rules = {
    'rule_type': 'sensor',
    'threshold_open': 0.,
    'threshold_close': 0,
    'comparison_open': 'notset',
    'comparison_close': 'notset',
    'mode': 'auto',
    'period': 0
}

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
        host=env_config['db']['host'],
        user=env_config['db']['user'],
        passwd=env_config['db']['pwd'],
        db=env_config['db']['dbname'],
        port=int(env_config['db']['port'])
    )
    cb_db.generate_mapping(check_tables=False)
    # cb_db.drop_all_tables(with_all_data=True) # used to clean testcase
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
            account_set=test_account,
            ag_token="testagtoken",
            mac_addr=uuid.uuid4()
        )

        test_rule = UserRule(
            rule_type='Sensor',
            actuator_alias='test_actuator',
            sa=test_sa,
            mode='auto'
        )

        test_account.sa_set.add(test_sa)
        test_sa.rule_set.add(test_rule)

        logger.info('\tTest database connection......done')
    except Exception as err:
        logger.error(err)

    return


def register_ag(sa, logger):
    '''
    Worker function to register to AG given sa entity and logger.

    Args:
        sa: SA entity object selected from PonyORM.
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating register status.
    '''
    try:
        running_sa[sa.cb_id] = sa 
        new_sa = open('./CB_SA.py', 'r').read().format(cb_id=sa.cb_id, config=reg_config, mac_addr=sa.mac_addr)
        data = {
            'version': 1,
            'code': new_sa
        }

        response = requests.post('http://140.113.215.12:8000/autogen/create_device', data=data).text
        sa.set(ag_token=response)
        return True

    except KeyError:
        logger.error('CB_SA key argument wrong, check parameter passed in or brackets in the code')
        return False

    except Exception as err:
        logger.error(err)
        return False


def deregister_ag(sa, logger):
    '''
    Worker function to deregister AG device.

    Args:
        sa: SA entity object selected from PonyORM.
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating register status.
    '''

    try:
        data = {
            'token': sa.ag_token
        }
        requests.post('http://140.113.215.12:8000/autogen/delete_device', data=data)

        with orm.db_session():
            CB_SA[sa.cb_id].delete()
        return True
    except Exception as err:
        logger.error(err)
        return False