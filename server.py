import time
import threading
import datetime


from flask import Flask
from flask import render_template
from flask import request
from flask import jsonify


import DAN
import models
import shared_vars


from config import env_config
from pulling_thread import on_data
from pushing_thread import on_check, logger


app = Flask(__name__)


@app.before_first_request
def init():
    """
    Initialization of CB SA.
    Clear memory, restore memory with rule_infos from db. Create pulling/pushing threads from IoTTalk server.

    Args:
        None

    Returns:
        None
    """
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
        shared_vars.rule_info[rule.actuator_alias]['status'] = 'green'
    print("restored rules from database:", shared_vars.rule_info)

    # Find corresponding mapping between sensor and actuator
    for i in range(env_config.max_thresholds):
        try:
            alias_in = DAN.get_alias('Threshold' + '-O' + str(i + 1))[0]
            alias_out = DAN.get_alias('Trigger' + '-I' + str(i + 1))[0]
            alias_in = alias_in.replace('-O', '')
            alias_out = alias_out.replace('-I', '')
            if 'Threshold' not in alias_in:
                shared_vars.mappings[alias_out] = (alias_in, i)
        except IndexError:
            print('less thresholds than max_threshold')

    print('mappings:', shared_vars.mappings)

    # create a thread to pull sensors' datum from IoTTalk Server
    x = threading.Thread(target=on_data, daemon=True)
    x.start()

    # Create corresponding thread for each rules stored in database
    for actuator in shared_vars.rule_info:
        if not (shared_vars.rule_info[actuator]['comparison_open'] == 'notset' and shared_vars.rule_info[actuator]['comparison_close'] == 'notset'):
            t = threading.Thread(target=on_check, args=(actuator, ), daemon=True)
            shared_vars.pushing_thread_dict[actuator] = [t, True]
            t.start()

    return


@app.route('/')
def main_page():
    """
    API for UI rendering.
    Checks alias changes before render template.

    Returns:
        Template UI
    """
    check_alias_on_load()
    return render_template('index.html')


@app.route('/new_rules', methods=['POST'])
def get_setting_condition():
    """
    API for accepting new rules .
    Take http requests, identify invalid settings, update valid settings.

    Returns:
        Http status code & rule setup msg.
    """
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
        print(invalid_sensors)
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

        if actuator_alias not in shared_vars.rule_info:
            shared_vars.rule_info[actuator_alias] = rule_settings
            shared_vars.rule_info[actuator_alias]['trigger'] = False
            shared_vars.rule_info[actuator_alias]['status'] = 'green'
        else:
            trigger, status = shared_vars.rule_info[actuator_alias]['trigger'], shared_vars.rule_info[actuator_alias]['status']
            shared_vars.rule_info[actuator_alias] = rule_settings
            shared_vars.rule_info[actuator_alias]['trigger'] = trigger
            shared_vars.rule_info[actuator_alias]['status'] = status

        if actuator_alias not in shared_vars.pushing_thread_dict:
            t = threading.Thread(target=on_check, args=(actuator_alias,), daemon=True)
            shared_vars.pushing_thread_dict[actuator_alias] = [t, True]
            t.start()
        else:
            print(actuator_alias)

    print(shared_vars.rule_info)

    return jsonify({
        'state': 'ok',
        'msg': 'Setup Threshold Done'
    }), 200


@app.route('/stop')
def stop_execution():
    """
    API for stoping all rule checking & actuator.
    Reset all rules in db. Stop actuator.

    Returns:
        Http status code & stop procedure execution msg.
    """
    rules = models.UserRule.select_all()

    for rule in rules:
        if rule.rule_type == 'sensor':
            models.UserRule.update_rules(actuator_alias=rule.actuator_alias, rule_type='sensor', comparison_open='notset', comparison_close='notset')
        else:
            models.UserRule.update_rules(actuator_alias=rule.actuator_alias, rule_type='timer', exetime=0)

        order = shared_vars.mappings[rule.actuator_alias][1]
        actuat_name = 'Trigger' + '-I' + str(order + 1)
        DAN.push(actuat_name, 0)
        if rule.actuator_alias in shared_vars.pushing_thread_dict:
            shared_vars.pushing_thread_dict[rule.actuator_alias][1] = False

    logger.info('API STOP called, push 0 to all actuators.')

    for t in shared_vars.pushing_thread_dict:
        th = shared_vars.pushing_thread_dict[t][0]
        th.join()

    shared_vars.rule_info.clear()
    shared_vars.pushing_thread_dict.clear()

    return jsonify({
        'state': 'ok',
        'msg': 'Stop execution succeeded'
    }), 200


@app.route('/rules', methods=['GET'])
def get_rule_data():
    """
    API for UI's rule execution status update.
    Get the settings of rules from memory.

    Returns:
        Http status code & a List of json records. Each json record indicates the status of corresponding rule.

    """
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
        print(actuator_alias, found)

    return jsonify(res_list), 200


@app.route('/current_data', methods=['GET'])
def get_current_data():
    """
    API for UI's sensor data update.
    Get the data from IoTTalk server which is stored in memory.

    Returns:
        Http status code & a json record indicating the lastest data of each sensor.
    """
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
            status = 'green'

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


def check_alias_on_load():
    """
    Checks alias changes every time UI rendered.
    When refreshing the web page, check for alias changes and update accordingly.

    Args:
        None

    Returns:
        None
    """
    alias_in = list()
    alias_out = list()
    shared_vars.pulling_flag = False
    time.sleep(3)
    # When page refreshes check for alias change
    # Get all actuator and sensor alias
    for i in range(env_config.max_thresholds):
        try:
            alias_i = DAN.get_alias('Threshold' + '-O' + str(i + 1))[0]
            alias_o = DAN.get_alias('Trigger' + '-I' + str(i + 1))[0]
            alias_in.append(alias_i.replace('-O', ''))
            alias_out.append(alias_o.replace('-I', ''))
        except IndexError:
            print('less thresholds than max_threshold')
    shared_vars.pulling_flag = True
    # if actuator alias changes, clear
    remove = [actuator_detect for actuator_detect in shared_vars.rule_info if actuator_detect not in alias_out]
    for actuator_delete in remove:
        if actuator_delete in shared_vars.pushing_thread_dict:
            shared_vars.pushing_thread_dict[actuator_delete][1] = False

            actuant_del = 'Trigger' + '-I' + str(shared_vars.mappings[actuator_delete][1] + 1)
            DAN.push(actuant_del, 0)
            shared_vars.rule_info.pop(actuator_delete, None)

        shared_vars.mappings.pop(actuator_delete, None)
        models.UserRule.delete_actuator_alias(actuator_delete)

    # Check if the actuator's alias is mapped or not
    for actuator in alias_out:
        index = alias_out.index(actuator)

        # If actuator's alias is mapped, check if sensor alias changed or not
        if actuator in shared_vars.rule_info:
            if actuator in shared_vars.mappings:
                sensor = shared_vars.mappings[actuator][0]
            # Sensor doesn't change, do nothing. Else, update to database
            if alias_in[index] == sensor:
                print("mapping not changed")
            else:
                actuant_del = 'Trigger' + '-I' + str(index + 1)
                DAN.push(actuant_del, 0)
                models.UserRule.delete_actuator_alias(actuator)

                # Filter writing dummy features into database
                if 'Trigger' not in actuator and 'Threshold' not in alias_in[index]:
                    models.UserRule.update_rules(actuator_alias=actuator, sensor_alias=alias_in[index], rule_type='sensor', comparison_open='notset', comparison_close='notset')
                    shared_vars.rule_info.update({
                        actuator: {
                            "rule_type": "sensor",
                            "actuator_alias": actuator,
                            "sensor_alias": alias_in[index],
                            "comparison_open": "notset",
                            "comparison_close": "notset",
                            "threshold_open": None,
                            "threshold_close": None,
                            "trigger": False,
                            "status": 'green'
                        }
                    })
                if 'Threshold' not in alias_in[index] and "Trigger" not in alias_out[index]:
                    shared_vars.mappings[actuator] = (alias_in[index], index)
                else:
                    shared_vars.mappings.pop(actuator, None)

        # actuator modified
        else:
            if 'Threshold' not in alias_in[index] and "Trigger" not in alias_out[index]:
                shared_vars.mappings[actuator] = (alias_in[index], index)
                models.UserRule.update_rules(actuator_alias=actuator, sensor_alias=alias_in[index], rule_type='sensor', comparison_open='notset', comparison_close='notset')
                shared_vars.rule_info.update({
                    actuator: {
                        "rule_type": "sensor",
                        "actuator_alias": actuator,
                        "sensor_alias": alias_in[index],
                        "comparison_open": "notset",
                        "comparison_close": "notset",
                        "threshold_open": None,
                        "threshold_close": None,
                        "trigger": False,
                        "status": 'green'
                    }
                })
            # t = threading.Thread(target=on_check, args=(actuator, ), daemon=True)
            # shared_vars.pushing_thread_dict[actuator] = (t, True)
            # t.start()
    x = threading.Thread(target=on_data, daemon=True)
    x.start()

    return


if '__main__' == __name__:
    DAN.profile = env_config.ctlboard_profile
    DAN.device_registration_with_retry(env_config.server_ip, env_config.mac_addr)
    # atexit.register(exit_handler)
    # os.chdir('/home/iottalk/controlboard')
    app.run(
        host=env_config.host,
        port=env_config.port,
        threaded=True
    )
