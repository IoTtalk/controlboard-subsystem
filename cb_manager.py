import datetime


from flask import Blueprint
from flask import render_template
from flask import request
from flask import jsonify


import DAN
import models
import shared_vars


instance_api = Blueprint('instance', __name__)


@instance_api.route('/new_rules', methods=['POST'])
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

    print (shared_vars.rule_info)

    return jsonify({
        'state': 'ok',
        'msg': 'Setup Threshold Done'
    }), 200


@instance_api.route('/stop')
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


@instance_api.route('/rules', methods=['GET'])
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


@instance_api.route('/current_data', methods=['GET'])
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
