import configparser
import sys


default_rules = {
    "threshold_open": 0.,
    "threshold_close": 0,
    "comparison_open": "notset",
    "comparison_close": "notset",
    "period": 0
}


config_path = str(sys.argv[1])
env_config = configparser.ConfigParser()
env_config.read(config_path)
use_v1 = env_config["IoTtalk"]["version"] == "1"
icon_extensions = env_config["env"]["icon_extensions"].split(",")

reg_config = {
    "database": env_config["db"]["database"],
    "host": env_config["db"]["host"],
    "user": env_config["db"]["user"],
    "pwd": env_config["db"]["pwd"],
    "dbname": env_config["db"]["dbname"],
    "port": env_config["db"]["port"],
    "iottalk_server": env_config["IoTtalk"]["ServerIP"]
}
