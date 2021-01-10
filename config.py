import configparser
import datetime
import sys


default_rules = {
    "threshold_open": 0.,
    "threshold_close": 0,
    "comparison_open": "notset",
    "comparison_close": "notset",
    "time_open": datetime.time(0, 0, 0),
    "time_close": datetime.time(0, 0, 0),
    "sensor_index": 0,
    "duty_pos": 0,
    "duty_neg": 0,
    "weekday": ""
}


default_status = {
    "prevTrigger": -10000,
    "status": False,
    "time": "00:00",
    "value": 0
}


config_path = str(sys.argv[1])
env_config = configparser.ConfigParser()
env_config.read(config_path)
use_v1 = env_config["IoTtalk"]["version"] == "1"
if not use_v1:
    raise NotImplementedError
icon_extensions = env_config["env"]["icon_extensions"].split(",")

reg_config = {
    "database": env_config["db"]["database"],
    "host_db": env_config["db"]["host"],
    "port_db": env_config["db"]["port"],
    "user": env_config["db"]["user"],
    "pwd": env_config["db"]["pwd"],
    "dbname": env_config["db"]["dbname"],
    "iottalk_server": env_config["IoTtalk"]["ServerIP"],
    "host_zmq": env_config["env"]["host"],
    "port_zmq": env_config["env"]["port_zmq"]
}
