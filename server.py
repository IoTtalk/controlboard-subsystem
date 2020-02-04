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


app = Flask(__name__)


@app.before_first_request
def init():
    shared_vars.mappings.clear()
    models.rule_db.generate_mapping(create_tables=True)
    # set_sql_debug(True)

    # Wait for registration done
    """
    while DAN.state == 'SUSPEND':
        print('Please bind Control Board Device on Iottalk GUI first')
        time.sleep(2)
    """

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

    # create a thread to pull sensors' datum from IoTTalk Server
    t = threading.Thread(target=on_data, daemon=True)
    t.start()

    # Create corresponding thread for each rules stored in database
    for actuator in shared_vars.rule_info:
        t = threading.Thread(target=on_check, args=(actuator, ), daemon=True)
        shared_vars.pushing_thread_dict[actuator] = t
        t.start()

    return


@app.route('/')
def main_page():
    return render_template('index.html')


@app.route('/new_rules', methods=['POST'])
def get_setting_condition():
    # Abnormal setting detection block
    invalid_list = list()
    for rule_settings in request.json:
        print(rule_settings)
        if rule_settings["rule_type"] == "sensor":
            if rule_settings['comparison_open'] != 'notset' and float(rule_settings["threshold_open"]) < 0.0:
                invalid_list.append(rule_settings['sensor_alias'])
            elif rule_settings['comparison_close'] != 'notset' and float(rule_settings["threshold_close"]) < 0.0:
                invalid_list.append(rule_settings['sensor_alias'])
                
    if invalid_list:
        invalid_sensors = str()
        for sensor_alias in invalid_list:
            invalid_sensors += (sensor_alias + ' ')
        print (invalid_sensors)
        return jsonify({
            'state': 'error',
            'msg': f'Abnormal threshold setting of {invalid_sensors}detected, aborting all'
        }), 400

    for rule_settings in request.json:
        print("dealing rule: ", rule_settings)
        actuator_alias = rule_settings['actuator_alias']
        if rule_settings['rule_type'] == 'timer':
            time_open = datetime.datetime.strptime(rule_settings['time_open'], '%H:%M:%S').time()
            time_close = datetime.datetime.strptime(rule_settings['time_close'], '%H:%M:%S').time()

            rule_settings['time_open'] = time_open
            rule_settings['time_close'] = time_close

        models.UserRule.update_rules(**rule_settings)

        shared_vars.rule_info[actuator_alias] = rule_settings
        shared_vars.rule_info[actuator_alias]['trigger'] = False
        shared_vars.rule_info[actuator_alias]['status'] = 'red'
        if actuator_alias not in shared_vars.pushing_thread_dict:
            t = threading.Thread(target=on_check, args=(actuator_alias,), daemon=True)
            shared_vars.pushing_thread_dict[actuator_alias] = t
            t.start()
        else:
            print (actuator_alias)

    print (shared_vars.rule_info)

    return jsonify({
        'state': 'ok',
        'msg': 'Setup Threshold Done'
    }), 200


@app.route('/stop')
def stop_execution():
    rules = models.UserRule.select_all()

    for rule in rules:
        shared_vars.pushing_flag = False
        if rule.rule_type == 'sensor':
            models.UserRule.update_rules(actuator_alias=rule.actuator_alias, rule_type='sensor', comparison_open='notset', comparison_close='notset')
        else:
            models.UserRule.update_rules(actuator_alias=rule.actuator_alias, rule_type='timer', exetime=0)
        
        order = shared_vars.mappings[rule.actuator_alias][1]
        actuat_name = 'Trigger' + str(order + 1) + '-I'
        DAN.push(actuat_name, 0)
    
    for t in shared_vars.pushing_thread_dict.values():
        t.join()

    shared_vars.pushing_flag = True
    shared_vars.rule_info.clear()
    shared_vars.pushing_thread_dict.clear()

    return jsonify({
        'state': 'ok',
        'msg': 'Stop execution succeeded'
    }), 200


@app.route('/rules', methods=['GET'])
def get_rule_data():
    res_list = list()
    
    for actuator_alias, mappings in shared_vars.mappings.items():
        sensor_alias = mappings[0]
        found = False
        if actuator_alias in shared_vars.rule_info:
            rule = shared_vars.rule_info[actuator_alias]
            if rule['rule_type'] == 'sensor':
                res_list.append({
                    'sensor_alias': rule['sensor_alias'],
                    'actuator_alias': rule['actuator_alias'],
                    'comparison_open': rule['comparison_open'],
                    'threshold_open': rule['threshold_open'] if rule['comparison_open'] != 'notset' else None,
                    'comparison_close': rule['comparison_close'],
                    'threshold_close': rule['threshold_close'] if rule['comparison_close'] != 'notset' else None,
                    'rule_type': rule['rule_type']
                })
            else:
                res_list.append({
                    'sensor_alias': sensor_alias,
                    'actuator_alias': rule['actuator_alias'],
                    'time_open': rule['time_open'].strftime('%H:%M:%S'),
                    'time_close': rule['time_close'].strftime('%H:%M:%S'),
                    'exetime': rule['exetime'],
                    'rule_type': rule['rule_type']
                })
        else:
            res_list.append({
                'sensor_alias': sensor_alias,
                'actuator_alias': actuator_alias,
                'rule_type': None
            })
        print (actuator_alias, found)

    return jsonify(res_list), 200


@app.route('/current_data', methods=['GET'])
def get_current_data():
    res_dict = dict()
    for actuator_alias, rule_info in shared_vars.mappings.items():
        rule_type = None
        sensor_alias = rule_info[0]
        if sensor_alias in shared_vars.df_hist_val:
            val = shared_vars.df_hist_val[sensor_alias][-1]
        else:
            val = None

        if actuator_alias in shared_vars.rule_info:
            triggered = shared_vars.rule_info[actuator_alias]['trigger']
            rule_type = shared_vars.rule_info[actuator_alias]['rule_type']
            status = shared_vars.rule_info[actuator_alias]['status']
        else:
            triggered = False
            status = 'red'

        time = datetime.datetime.now().strftime('%H:%M')
            
        res_dict[sensor_alias] = {
            "value": val,
            "triggered": triggered,
            'rule_type': rule_type,
            'time': time,
            'status': status
        }
        
    return jsonify(res_dict), 200


def exit_handler():
    shared_vars.pulling_flag = False
    shared_vars.pushing_flag = False
    time.sleep(3)

    return


if '__main__' == __name__:
    DAN.profile = env_config.ctlboard_profile
    DAN.device_registration_with_retry(env_config.server_ip, env_config.mac_addr)
    # atexit.register(exit_handler)
    os.chdir('/home/iottalk/controlboard')
    app.run(
        host=env_config.host,
        port=env_config.port,
        threaded=True
    )
