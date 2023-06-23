import configparser
import datetime
import sys

sensor_default = {
    "threshold_open": 0,
    "threshold_close": 0,
    "comparison_open": "notset",
    "comparison_close": "notset",
    "operation": "AND",
    "is_show_operation": True
}

default_rules = {
    #"threshold_open": 0.,
    #"threshold_close": 0,
    #"comparison_open": "notset",
    #"comparison_close": "notset",
    "time_open": datetime.time(0, 0, 0),
    "time_close": datetime.time(0, 0, 0),
    #"sensor_index": 0,
    "duty_pos": 0,
    "duty_neg": 0,
    "weekday": "",
    #"operation":""
}


default_status = {
    "prevTrigger": -10000,
    "status": False,
    "time": "00:00",
    "value": 0
}


config_path = str(sys.argv[1]) #store file name by using sys.argv[1] to string
env_config = configparser.ConfigParser() #build a configparser event
env_config.read(config_path)
use_v1 = env_config["IoTtalk"]["version"] == "1"
if not use_v1:
    raise NotImplementedError
icon_extensions = env_config["env"]["icon_extensions"].split(",") #["png","svg"]

reg_config = {
    "iottalk_server": env_config["IoTtalk"]["ServerIP"],
    "host_zmq": env_config["env"]["host"],
    "port_zmq": env_config["env"]["port_zmq"],
    "mqtt_broker": env_config["MQTT"]["MQTT_broker"],
    "mqtt_port": env_config["MQTT"]["MQTT_port"],
    "mqtt_encryption": env_config["MQTT"]["MQTT_encryption"],
    "mqtt_User": env_config["MQTT"]["MQTT_User"],
    "mqtt_PW": env_config["MQTT"]["MQTT_PW"],
}
