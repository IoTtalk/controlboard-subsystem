import datetime
import uuid


from flask import Blueprint
from flask import jsonify
from flask import render_template
from flask import request
from pony import orm


from config import env_config
from utils import running_sa
from utils import make_logger
from utils import register_ag, deregister_ag
from utils import create_proj_ag
from models import cb_db
from models import UserRule, CB_Account, CB_SA, CB_Status


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
    raise NotImplementedError
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
        actuator_alias = rule_settings['actuator_alias']
        if rule_settings['rule_type'] == 'timer':
            time_open = datetime.datetime.strptime(rule_settings['time_open'], '%H:%M:%S').time()
            time_close = datetime.datetime.strptime(rule_settings['time_close'], '%H:%M:%S').time()

            rule_settings['time_open'] = time_open
            rule_settings['time_close'] = time_close

        with orm.db_session():
            sa = CB_SA[cb_id]
            try:
                rule = UserRule.get(sa=sa, actuator_alias=actuator_alias)
                rule.set(**rule_settings)
            except orm.RowNotFound:
                new_rule = UserRule(
                    
                )
            except orm.MultipleRowsFound:
                pass
            
            if cb_id in running_sa:
                # ag delete api
                pass

            rule = get(lambda r: r.sa.cb_id == sa.cb_id and r.actuator_alias == actuator_alias)[:] 
            if rules:
                for rule in rules:
                    tmp = rule.to_dict()
                    if tmp["actuator_alias"] == actuator_alias:
                        rule.set(**rule_settings)
            else:
                new_rule = UserRule(**rule_settings, sa=sa)
                new_status = CB_Status(rule_id=new_rule.rule_id, status='green', value=0.0)

        ''' TODO
            1. Delete original SA if already running
            2. Create new SA
        '''
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
    with orm.db_session():
        sa = CB_SA[cb_id]
        #rules = select("select * from UserRule where sa = $sa")[:]  # TODO Not sure if SQL correct or not.
        rules = UserRule.select(lambda ur: ur.sa.cb_id == sa.cb_id)[:]
        for rule in rules:
            tmp = rule.to_dict()
            if tmp['sa'] == sa.cb_id:
                if tmp['rule_type'] == 'sensor':
                    rule.set(comparison_close = 'notset', comparison_open='notset')
                else:
                    rule.set(exetime=0)

        #order = running_sa[cb_id].mappings[rule.actuator_alias][1]
        #actuat_name = 'Trigger' + '-I' + str(order + 1)
        #DAN.push(actuat_name, 0)

    #running_sa[cb_id].rules.clear()

    return jsonify({
        'state': 'ok',
        'msg': 'Stop Done'
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
                   Each element of this list is a rule in dictionary format.

    '''
    res_list = list()

    ''' 
    TODO wrong attributes, should be
        1. fetch all rules of this sa by `cb_id`
        2. for each rule, collect needed information in UserRule Entity

        Note that status are combined to API `current_data` to return.
    '''
    """
    for actuator_alias, mappings in running_sa[cb_id].mappings.items():
        sensor_alias = mappings[0]
        if actuator_alias in running_sa[cb_id].rules:
            rule = running_sa[cb_id].rules[actuator_alias]
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
    """
    with orm.db_session():
        sa = CB_SA[cb_id]
        rules = UserRule.select(lambda r: r.sa.cb_id == sa.cb_id)[:]
        for rule in rules:
            tmp = rule.to_dict()
            if tmp['rule_type'] == 'sensor':
                res_list.append({
                    'sensor_alias': tmp['sensor_alias'],
                    'actuator_alias': tmp['actuator_alias'],
                    'comparison_open': tmp['comparison_open'],
                    'threshold_open': tmp['threshold_open'] if tmp['comparison_open'] != 'notset' else None,
                    'comparison_close': tmp['comparison_close'],
                    'threshold_close': tmp['threshold_close'] if tmp['comparison_close'] != 'notset' else None,
                    'rule_type': tmp['rule_type']
                })
            else:
                res_list.append({
                    #'sensor_alias': sensor_alias,  # thinking about how to extract sensor_alias
                    'actuator_alias': tmp['actuator_alias'],
                    'time_open': tmp['time_open'].strftime('%H:%M:%S'),
                    'time_close': tmp['time_close'].strftime('%H:%M:%S'),
                    'exetime': tmp['exetime'],
                    'rule_type': tmp['rule_type']
                })
    
    return jsonify(res_list), 200


@apis.route('/sa/<cb_id>/current_data', methods=['GET'])
def get_datum(cb_id):
    '''
    Get the datum of sensors manipulated by the specified SA.

    Args:
        cb_id: ID of the requester SA.

    Returns:
        Status code: 200.
        record_list: A json object containing the lastest data of each sensor and trigger status.
    '''

    #  TODO: update this API to contain trigger status
    
    record_list = list()
    res_dict = dict()
    cbstatus = dict()
    with orm.db_session():
        sa = CB_SA[cb_id]
        rules = UserRule.select(lambda ur: ur.sa.cb_id == sa.cb_id)[:]
        for rule in rules:
            tmp = rule.to_dict()
            stats = CB_Status.select(lambda s: s.rule_id == tmp['rule_id'])  # one rule one status, can use get but select is better for testing
            
            for stat in stats:
                cbstatus[tmp['actuator_alias']] = stat.status

    for actuator_alias, rule_info in running_sa[cb_id].mappings.items():
        rule_type = None
        sensor_alias = rule_info[0]
        if sensor_alias in running_sa[cb_id].df_hist_val:
            val = running_sa[cb_id].df_hist_val[sensor_alias][-1]
        else:
            val = None


        if actuator_alias in running_sa[cb_id].rules:
            rule_type = running_sa[cb_id].rules[actuator_alias]['rule_type']
            #status = running_sa[cb_id].rules[actuator_alias]['status']
            status = cbstatus[actuator_alias]
        else:
            status = 'green'
        
        time = datetime.datetime.now().strftime('%H:%M')

        res_dict[sensor_alias] = {
            "value": val,
            'rule_type': rule_type,
            'time': time,
            'status': status
        }
    #return jsonify(record_list), 200
    return jsonify(res_dict), 200


@apis.route('/subsystem/create_sa', methods=['POST'])
def create_sa():
    '''
    Creates an empty SA.

    Args:
        account: The user's account who requests for this new SA.
        cb_name: Name of this SA given by the user.
        mappings: User-specified (sensor, actuator) pairs. Used to create project.

    Returns:
        Status code: 200.
        proj_name: Project name for user to choose input sensors and output actuators.
    '''
    with orm.db_session():
        mac_addr = str(uuid.uuid4())
        sa = CB_SA(cb_name='TestSA', ag_token='NotCreated', mac_addr=mac_addr)
        cb_db.commit()
        api_logger.info(f'Create New SA, SA_ID: {sa.cb_id}')
        # status = register_ag(sa, api_logger)
        create_proj_ag('test_proj', api_logger)

    # if status:
        return "Create SA succeeded", 200
    # else:
    #     return "Create SA failed, check api log files", 400



@apis.route('/subsystem/delete_sa/<cb_id>', methods=['POST'])
def delete_sa(cb_id):
    '''
    Delete SA with specified cb_id.
        
    Args:
        cb_id: ID of the requester SA.

    Returns:
        Status code: 200.
        message: 'SA deleted successfully'.
    '''
    try:
        sa = running_sa[int(cb_id)]
        status = deregister_ag(sa, api_logger)
        api_logger.info(f"Delete Running SA, SA_ID: {sa.cb_id}")
        if status:
            return "Delete SA succeeded", 200
        else:
            return "Delete SA failed, check api log files", 502
    except KeyError:
        api_logger.info('Specified ControlBoard not running')
        return "Specified SA not found", 400
    



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
    avail_sa = list()
    with orm.db_session():
        accs = CB_Account.select(lambda a: a.account == usr_account)[:]
        for acc in accs:
            acc_dict = acc.to_dict()
            for sa in acc.sa_set:
                avail_sa.append((sa.cb_id, sa.cb_name))
        
    print(avail_sa)
    return avail_sa, 200   # GET return cannot be list, must be dict or string or something... need to decide which type to use


@apis.route('/account/create', methods=['POST'])
def create_account():
    # for account_info in request.json:
        
    pass
