import requests


from flask import Blueprint
from flask import jsonify
from flask import render_template
from flask import request


from utils import make_logger
from utils import config


api_logger = make_logger('API', 'API')
apis = Blueprint('api', __name__)


@apis.route('/sa/<cb_id>/')
def render_SA(cb_id):
    '''
    Render SA template of the SA with specified cb_id.

    Args:
        cb_id: ID of the requester SA.

    Returns:
        Rendered HTML template of the SA.
        Status code: 200.
    '''

    # js need to add get_rules(cb_id) first
    return render_template("index.html"), 200


@apis.route('/sa/<cb_id>/new_rules', methods=['POST'])
def set_rules(cb_id):
    '''
    Set the rules contained in the request sent from the specified SA.

    Args:
        cb_id: ID of the requester SA.

    Returns:
        Status code: 200.
    '''
    # Iterate through the list of SA and find the one with cb_id == sa_id
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

        SA_dict[cb_id].update_rules(actuator_alias, rule_settings)

    return jsonify({
        'state': 'ok',
        'msg': 'Setup Threshold Done'
    }), 200


@apis.route('/sa/<cb_id>/stop', methods=['GET'])
def stop_SA(cb_id):
    '''
    Stop all actuator execution and pends the SA with specified cb_id.

    Args:
        cb_id: ID of the requester SA.

    Returns:
        Status code: 200.
        message: 'Stop Done'.
    '''

    SA_dict[cb_id].terminate()

    return jsonify({
        'state': 'ok',
        'msg': 'Stop execution succeeded'
    }), 200


@apis.route('/sa/<cb_id>/rules', methods=['GET'])
def get_rules(cb_id):
    '''
    Get the rules contained in the specified SA.

    Args:
        cb_id: ID of the requester SA.

    Returns:
        Status code: 200.
        rule_list: A list containing rules of the specific SA.
                   Each element of this list is a rule in dictionary format and it's current status and mode.

    '''
    #iterate through the list of SA and find the one with cb_id == sa_id, replace CB_SA with that one
    res_list = list()
    for actuator_alias, mappings in SA_dict[cb_id].mappings.items():
        sensor_alias = mappings[0]
        if actuator_alias in SA_dict[cb_id].rules:
            rule = SA_dict[cb_id].rules[actuator_alias]
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


@apis.route('/sa/<cb_id>/current_data', methods=['GET'])
def get_datum(cb_id):
    '''
    Get the datum of sensors manipulated by the specified SA.

    Args:
        cb_id: ID of the requester SA.

    Returns:
        Status code: 200.
        record_list: A json object containing the lastest data of each sensor.
    '''
    #iterate through the list of SA and find the one with cb_id == sa_id
    record_list = list()
    for actuator_alias, rule_info in SA_dict[cb_id].mappings.items():
        rule_type = None
        sensor_alias = rule_info[0]
        if sensor_alias in SA_dict[cb_id].df_hist_val:
            val = SA_dict[cb_id].df_hist_val[sensor_alias][-1]
        else:
            val = None

        if actuator_alias in SA_dict[cb_id].rules:
            triggered = SA_dict[cb_id].rules[actuator_alias]['trigger']
            rule_type = SA_dict[cb_id].rules[actuator_alias]['rule_type']
            status = SA_dict[cb_id].rules[actuator_alias]['status']
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

    return jsonify(record_list), 200


@apis.route('/subsystem/create_sa', methods=['POST'])
def create_sa():
    '''
    Creates SA with specified actuator/sensor alias.

    Args:


    Returns:
        Status code: 200.
        proj_name: Project name for user to choose input sensors and output actuators.
    '''
    test_mappings = {
        'test_actuator_alias': ('test_sensor_alias', 0)
    }
    db_info = config['db']
    print(db_info)
    new_sa = open('./CB_SA.py', 'r').read().format(account='test', mappings=test_mappings, db_info=db_info)
    api_logger.info('Create New SA')

    data={
        'version': 1,
        'code': new_sa
    }

    requests.post('http://127.0.0.1:8000/autogen/create_device', data=data)

    return new_sa, 200


@apis.route('/subsystem/delete_sa/<cb_id>', methods=['GET'])
def delete_sa(cb_id):
    '''
    Delete SA with specified cb_id.
        1. Deregister DA.
        2. Remove corresponding project on IoTtalk.
        3. Clear Database records.
        
    Args:
        cb_id: ID of the requester SA.

    Returns:
        Status code: 200.
        message: 'SA deleted successfully'.
    '''
    #iterate through the list of SA and find the one with cb_id == sa_id, delete it with help of autogen(?)
    SA_dict[cb_id].deregister()  # add deregister function
    models.CB_SA.delete_sa(cb_id)  #need to add this function
    models.CB_Account.delete_avai_sa(cb_id) #need to add this function
    pass


@apis.route('/subsystem/get_sa/<usr_account>', methods=['GET'])
def get_sa(usr_account):
    '''
    Get accessible cb_ids and cb_names of the specified user. Called when rendering SAs available to the user.

    Args:
        usr_account: the account of the user.

    Returns:
        Status code: 200.
        avail_sa: A list of CB SAs, each element is composed of cb_id and cb_name of the corresponging SA.
    '''
    usr_sa = list()
    usr_sa = models.CB_Account.list_sa(usr_account) #need to add this function, return list (cb_id, cb_name)
    return usr_sa, 200
    pass


@apis.route('/account/create', methods=['POST'])
def create_account():
    for account_info in request.json:
        models.CB_Account.signup(account_info) #need to add this function
    pass
