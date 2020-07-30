import configparser
import sys


default_rules = {
    'rule_type': 'sensor',
    'threshold_open': 0.,
    'threshold_close': 0,
    'comparison_open': 'notset',
    'comparison_close': 'notset',
    'mode': 'auto'
}


config_path = str(sys.argv[1])
env_config = configparser.ConfigParser()
env_config.read(config_path)
use_v1 = env_config['IoTtalk']['version'] == '1'

reg_config = {
    'host': env_config['db']['host'],
    'user': env_config['db']['user'],
    'pwd': env_config['db']['pwd'],
    'dbname': env_config['db']['dbname'],
    'port': env_config['db']['port'],
    'iottalk_server': env_config['IoTtalk']['ServerIP']
}
