import time
import threading
import logging
import datetime
import atexit
import os


from flask import Flask
from flask import render_template
from flask import request
from flask import jsonify
from pony.orm import set_sql_debug


import DAN
import models
import shared_vars


from config import env_config
from pulling_thread import on_data
from pushing_thread import on_check
from cb_manager import instance_api


app = Flask(__name__)
app.register_blueprint(instance_api)


@app.before_first_request
def init():
    shared_vars.mappings.clear()
    models.cb_db.generate_mapping(create_tables=True)
    # set_sql_debug(True)

    # restore rules from database 
    rules = models.UserRule.select_all()
    for rule in rules:
        shared_vars.rule_info[rule.actuator_alias] = rule.to_dict()
        shared_vars.rule_info[rule.actuator_alias]["trigger"] = False
        shared_vars.rule_info[rule.actuator_alias]['status'] = 'red'
    print ("restored rules from database:", shared_vars.rule_info)

    # Find corresponding mapping between sensor and actuator
    for i in range(env_config.max_thresholds):
        alias_in = DAN.get_alias('Threshold' + str(i + 1) + '-O')[0]
        alias_out = DAN.get_alias('Trigger' + str(i + 1) + '-I')[0]
        alias_in = alias_in[:-2]
        alias_out = alias_out[:-2]
        if 'Threshold' not in alias_in:
            shared_vars.mappings[alias_out] = (alias_in, i)
    print('mappings:', shared_vars.mappings)

    # create a thread to pull sensors' datum from IoTTalk Server.
    t = threading.Thread(target=on_data, daemon=True)
    t.start()

    # create a thread to push actuator trigger status.
    t = threading.Thread(target=on_check,  daemon=True)
    t.start()

    return


@app.route('/')
def main_page():
    return render_template('index.html')



def exit_handler():
    shared_vars.pulling_flag = False
    shared_vars.pushing_flag = False
    time.sleep(3)

    return


if '__main__' == __name__:
    DAN.profile = env_config.ctlboard_profile
    DAN.device_registration_with_retry(env_config.server_ip, env_config.mac_addr)
    # atexit.register(exit_handler)
    app.run(
        host=env_config.host,
        port=env_config.port,
        threaded=True
    )
