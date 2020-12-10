import datetime
import os
import uuid


from flask import Blueprint
from flask import jsonify
from flask import render_template
from flask import request
from flask import session
from flask import redirect
from pony import orm


from utils import running_sa, running_status
from utils import make_logger
from utils import create_proj_ag, delete_proj_ag
from utils import create_do_ag
from utils import register_ag, deregister_ag, bind_device_ag
from models import cb_db
from models import UserRule, CB_Account, CB_SA, CB
from config import default_rules
from config import use_v1


api_logger = make_logger('API', 'API')
apis = Blueprint('api', __name__)
logined_user = dict()


@apis.route('/', methods=["GET"])
def render_index():
    '''
    Render Function of main page.

    Args: None

    Returns:
        Rendered HTML template of the SA.
        Status code: 200.
    '''
    session["token"] = str(uuid.uuid4())
    logined_user[session["token"]] = "test"
    return render_template("main.html")


@apis.route('/sa/<sa_id>/new_rules', methods=['POST'])
@orm.db_session
def set_rules(sa_id):
    '''
    Set the rules contained in the request sent from the specified SA.

    Args:
        sa_id: ID of the requester SA.
        request: A list of rule settings in json format.

    Returns:
        Status code:
            200: Successfully setup rules.
            400: Invalid rule settings detected.
            502: Internal Error occured.
        msg: Depends on status code.
            200: "Configuration Saved".
            400: a string containing invalid actuators.
            502: "Internal Server Error".
    '''
    api_logger.info(f'Start setting new rules of SA NO. {sa_id}')
    invalid_list = list()
    for rule_settings in request.json:
        print(rule_settings)
        invalid = False
        # Sensor threshold setup < 0
        if rule_settings["rule_type"] == "sensor":
            if rule_settings["comparison_open"] != "notset" and float(rule_settings["threshold_open"]) < 0.0:
                invalid = True
            elif rule_settings["comparison_close"] != "notset" and float(rule_settings["threshold_close"]) < 0.0:
                invalid = True

        # Period > 0 but no exetime
        if int(rule_settings["period"]) > 0:
            if rule_settings["exetime"] is None or int(rule_settings["exetime"]) <= 0:
                invalid = True

        if invalid:
            invalid_list.append(rule_settings["actuator_alias"])

    if invalid_list:
        invalid_actuators = str()
        for actuator_alias in invalid_list:
            invalid_actuators += (actuator_alias + ' ')
        api_logger.info(f'Invalid new rules of SA NO. {sa_id} detected, abort all.')
        return f'Abnormal threshold setting of {invalid_actuators}detected, aborting all', 400

    api_logger.info('\tStart setting rules')
    sa = CB_SA[sa_id]
    for rule_settings in request.json:
        actuator_alias = rule_settings['actuator_alias']
        if rule_settings['rule_type'] == 'timer':
            time_open = datetime.datetime.strptime(rule_settings['time_open'], '%H:%M:%S').time()
            time_close = datetime.datetime.strptime(rule_settings['time_close'], '%H:%M:%S').time()

            rule_settings['time_open'] = time_open
            rule_settings['time_close'] = time_close

        try:
            rule = UserRule.get(sa=sa, actuator_alias=actuator_alias)
            rule.set(**rule_settings)
        except orm.RowNotFound:
            UserRule(
                **default_rules,
                actuator_alias=actuator_alias,
                sa=sa
            )
        except orm.MultipleRowsFound:
            api_logger.error("Error creating new rule, Multiple Rules for the same mapping found")
            return "Internal Server Error", 502

    if sa_id in running_sa:
        status = deregister_ag(running_sa[sa_id], api_logger)
        if not status:
            api_logger.error("Error creating new rule, Change User configuraion failed, check API logs")
            return "Internal Server Error", 502

    status, ag_token = register_ag(sa, api_logger)
    if not status:
        api_logger.error("Error creating new rule, Change User configuraion failed, check API logs")
        return "Internal Server Error", 502
    sa.ag_token = ag_token
    running_sa[sa.sa_id] = sa

    do_id = [int(id) for id in sa.do_id.split(',')]
    status = bind_device_ag(sa.mac_addr, sa.p_id, do_id, api_logger)

    if not status:
        api_logger.error("Error creating new rule, Change User configuraion failed, check API logs")
        return "Internal Server Error", 502

    return 'Configuration Saved', 200


@apis.route('/sa/<sa_id>/stop', methods=['GET'])
@orm.db_session
def stop_SA(sa_id):
    '''
    Stop all actuator execution and pends the SA with specified sa_id.

    Args:
        sa_id: ID of the requester SA.

    Returns:
        Status code:
            200: All procedure succeeded.
            502: Some procedure failed, check API log files.
        msg: Depends on Status code.
            200: 'Stop Done'.
            502: 'Internal Server Error'.
    '''
    try:
        sa = running_sa[sa_id]
        rules = sa.rule_set

        for rule in rules:
            rule.set(**default_rules)

        if not deregister_ag(sa, api_logger):
            return f"stop SA {sa_id} failed at deregistering, check API log files", 502

        status, ag_token = register_ag(sa, api_logger)
        if not status:
            return f"stop SA {sa_id} failed at registering, check API log files", 502
        sa.ag_token = ag_token

        if not bind_device_ag(sa.mac_addr, sa.p_id, sa.do_id, api_logger):
            return f"stop SA {sa_id} failed at re-binding, check API log files", 502

        return 'Stop Done', 200
    except KeyError:
        return "Specified SA is not running", 400


@apis.route('/sa/<sa_id>/rules', methods=['GET'])
@orm.db_session
def get_rules(sa_id):
    '''
    Get the rules contained in the specified SA.

    Args:
        sa_id: ID of the requester SA.

    Returns:
        Status code: 200.
        rule_list: A list containing rules of the specific SA.
                   Each element of this list is a rule in dictionary format.

    '''
    res_list = list()
    try:
        sa = running_sa[sa_id]
        rules = UserRule.select(lambda r: r.sa.sa_id == sa.sa_id)[:]
    except KeyError:
        api_logger.info("Specified SA not running")
        return "Specified SA not running", 400

    for rule in rules:
        tmp = rule.to_dict()
        if tmp['rule_type'] == 'timer':
            tmp['time_open'] = tmp['time_open'].strftime('%H:%M:%S')
            tmp['time_close'] = tmp['time_close'].strftime('%H:%M:%S')

        res_list.append(tmp)

    return jsonify(res_list), 200


@apis.route('/sa/<sa_id>current_data', methods=['POST'])
@orm.db_session
def set_datum(sa_id):
    pass


@apis.route('/sa/<sa_id>/current_data', methods=['GET'])
@orm.db_session
def get_datum(sa_id):
    '''
    Get the datum of sensors manipulated by the specified SA.

    Args:
        sa_id: ID of the requester SA.

    Returns:
        Status code: 200.
        record_list: A json object containing the lastest data of each sensor and trigger status.
    '''
    res_dict = dict()
    try:
        rules = running_sa[sa_id].rule_set
    except KeyError:
        api_logger.error("Error getting SA's current data, Specified SA not running")
        return "Specified SA not running", 400

    for rule in rules:
        stats = running_status[sa_id][rule.sensor_alias]
        stats['time'] = datetime.datetime.now().strftime('%H:%M')
        res_dict[rule.sensor_alias] = stats

    return jsonify(res_dict), 200


@apis.route('/subsystem/create_sa', methods=['POST'])
def create_sa():
    '''
    Creates an empty SA.

    Args:
        account: The user's account who requests for this new SA.
        sa_name: Name of this SA given by the user.

    Returns:
        Status code: 200.
        proj_name: Project name for user to choose input sensors and output actuators.
    '''
    sa_spec = request.json
    with orm.db_session():
        mac_addr = str(uuid.uuid4())
        sa = CB_SA(sa_name=sa_spec['sa_name'], ag_token='NotCreated', mac_addr=mac_addr, p_id=-1, do_id='-1')
        cb_db.commit()
        api_logger.info("Start Creating CB SA")

        # Register device
        status, ag_token = register_ag(sa, api_logger)
        if not status:
            sa.delete()
            return "Create SA failed at registering device, check api log files", 400
        sa.ag_token = ag_token

        # Create Project
        status, p_id = create_proj_ag(sa, api_logger)
        if not status:
            deregister_ag(sa, api_logger)
            sa.delete()
            return "Create SA failed at creating project, check api log files", 400
        sa.p_id = p_id

        # Create Device Object
        status, do_id = create_do_ag(p_id, api_logger)
        if not status:
            deregister_ag(sa, api_logger)
            sa.delete()
            return "Create SA failed at creating DO, check api log files", 400
        if use_v1:
            sa.do_id = str(do_id[0]) + ',' + str(do_id[1])
        else:
            sa.do_id = str(do_id)

        # Bind device to DO
        status = bind_device_ag(sa.mac_addr, p_id, do_id, api_logger)
        if not status:
            deregister_ag(sa, api_logger)
            sa.delete()
            return "Create SA failed at auto binding, check api log files", 400

    running_sa[sa.sa_id] = sa
    api_logger.info(f'Create New SA, SA_ID: {sa.sa_id}')

    return "Create SA succeeded", 200


@apis.route('/subsystem/delete_sa/<sa_id>', methods=['POST'])
def delete_sa(sa_id):
    '''
    Delete SA with specified sa_id.

    Args:
        sa_id: ID of the requester SA.

    Returns:
        Status code: 200.
        message: 'SA deleted successfully'.
    '''
    try:
        sa = running_sa[int(sa_id)]
        status = deregister_ag(sa, api_logger)
        if not status:
            api_logger.error("Error delete SA, Deregister SA failed, check api log file")
            return "Delete SA failed, check api log files", 502

        status = delete_proj_ag(sa.p_id, api_logger)
        if not status:
            api_logger.error("Error delete SA, Delete project failed, check api log file")
            return "Delete SA failed, check api log files", 502

        api_logger.info(f"Delete Running SA, SA_ID: {sa.sa_id}")
        return "Delete SA succeed", 200
    except KeyError:
        api_logger.info('Specified ControlBoard not running')
        return "Specified SA not found", 400


@apis.route('/subsystem/get_sa/<usr_account>', methods=['GET'])
def get_sa(usr_account):
    '''
    Get accessible sa_ids and sa_names of the specified user. Called when rendering SAs available to the user.

    Args:
        usr_account: the account of the user.

    Returns:
        Status code: 200.
        avail_sa: A list of CB SAs, each element is composed of sa_id and sa_name of the corresponging SA.
    '''
    avail_sa = list()
    with orm.db_session():
        accs = CB_Account.select(lambda a: a.account == usr_account)[:]
        for acc in accs:
            # acc_dict = acc.to_dict()
            for sa in acc.sa_set:
                avail_sa.append((sa.sa_id, sa.sa_name))

    print(avail_sa)
    return avail_sa, 200   # GET return cannot be list, must be dict or string or something... need to decide which type to use


@apis.route('/subsystem/create_cb', methods=['POST'])
def create_cb():
    '''
    Create a Empty ControlBoard that contains no SA Field.

    Args:
        "text": cb_name of this ControlBoard.
        "shared": Whether to be seen by other users.

    Returns:
        Status Code: 200 / 401 / 500.
        Message: Corresponding execution result.
    '''
    api_logger.info("Create ControlBoard Triggered!")
    new_cb = request.json
    with orm.db_session():
        cb = CB(
            cb_name=new_cb["text"],
            shared=new_cb["shared"],
            icon="landscape.svg"
        )
        try:
            owner = CB_Account.get(account=logined_user[session["token"]])
            if None is owner:
                raise ValueError
            cb.account_set.add(owner)
        except KeyError:
            api_logger.error("Error Create CB, User not logined")
            return "User not logined", 401
        except ValueError:
            api_logger.error("Error Create CB, Non-existed User!")
            return "Non-existed User!", 401
        except Exception as err:
            api_logger.error(err)
            return "Unknown Error occurred, contact subsystem-admin to check error log!", 502
    return "Success", 200


@apis.route('/subsystem/delete_cb', methods=['POST'])
def delete_cb():
    '''
    Delete CB and corresponding SAs / UserRules with specified cb_id.

    Args:
        cb_id: ID of the specified retrived from function `get_cb`

    Returns:
        Status Code: 200 / 401 / 500.
        Message: Corresponding execution result.
    '''
    try:
        cb_id = request.get_data().decode("utf-8")
        with orm.db_session():
            account = CB_Account.get(account=logined_user[session["token"]])
            if not account.privilege:
                raise ValueError
            CB[cb_id].delete()  # By applying cascade deleting.
        return "Specified ControlBoard deleted."
    except KeyError:
        api_logger.error("Error Deleting ControlBoard, User not logined.")
        # TODO: redirect to AAA login page.
        return "Please login first", 401
    except ValueError:
        api_logger.error("Error Deleting ControlBoard, User is not a superuser.")
        return "Not a superuser!", 401
    except Exception as err:
        api_logger.error("Unknown error occurred, error message as belows")
        api_logger.error(err)
        return "Internal error occurred", 502


@apis.route('/subsystem/get_cb', methods=['GET'])
def get_cb():
    '''
    Returns Accessible CB list of current logined user

    Args: None

    Returns:
        Status code: 200 / 401
        accessible_cb: A Dict containing 2 lists
            accessibleProjects: A list containing all CB_ids owned/shared to this user.
            optionProjects: A list of CBs including all CBs shared to this user.

            If user is not a superuser, that `accessibleProjects` will be exactly the same as `optionProjects`.
            Otherwise `optionProjects` would contains all CBs.
    '''
    try:
        with orm.db_session():
            account = CB_Account.get(account=logined_user[session["token"]])
            if None is account:
                raise ValueError
            accessible_cb = list()
            for cb in account.cb_set:
                accessible_cb.append(cb.cb_id)

            option_cb = list()
            if account.privilege:
                candidates = CB.select()
            else:
                candidates = account.cb_set()
            for cb in candidates:
                icon_path = os.path.join("..", "static", "imgs", cb.icon)
                option_cb.append({
                    "icon": icon_path,
                    "text": cb.cb_name,
                    "value": cb.cb_id
                })
        return jsonify({
            "accessibleProjects": accessible_cb,
            "optionProjects": option_cb
        }), 200
    except KeyError:
        api_logger.error("Error Getting ControlBoard, User not logined.")
        # TODO: redirect to AAA login page.
        return "Please Login first", 401
    except ValueError:
        api_logger.error("Error Getting ControlBoard, No such user.")
        # TODO: redirect to AAA login page.
        return "No such User", 401


@apis.route('/account/login', methods=['GET', 'POST'])
def login():
    # TODO: add redirect to AAA procedures.
    account = request.json['account']
    password = request.json['']
    print(password)

    status = redirect('path.to.AAA')

    if status:
        try:
            usr = cb_db.get(lambda s: s.account == account)
            print(usr)
        except orm.RowNotFound:
            if request.method == 'GET':
                return "No such user"
            # Add new user
            usr = cb_db.CB_Account(account=account, privilege=0)
            print(usr)
        except Exception as err:
            api_logger.error('An error encountered when handling login, check the follow logs')
            api_logger.error(err)
    else:
        return "AAA login failed", 400

    session['username'] = account
    session['']

    return 'hello', 200
