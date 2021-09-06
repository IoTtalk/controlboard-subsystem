import datetime
from functools import wraps
import json
import requests
import time
import uuid


from flask import abort
from flask import Blueprint
from flask import jsonify
from flask import render_template
from flask import request
from flask import session
from flask import redirect
from flask import url_for
from pony import orm


from config import default_rules, default_status
from config import env_config
from config import use_v1
from email_tracker import email_notifier
from exceptions import NotAuthorizedError, NotFoundError, WrongSettingError, CCMAPIFailError
from oauth import oauth2_client
from utils import running_cb, running_status, iottalk_info
from utils import make_logger
from utils import create_proj_ag, delete_proj_ag, get_proj_ag
from utils import create_do_ag, delete_do_ag
from utils import register_ag, deregister_ag, bind_device_ag
from utils import get_na_ag, delete_na_ag, set_fn_ag, create_na_ag
from models import cb_db
from models import CBElement, CB_Account, CB


api_logger = make_logger('API', 'API')
apis = Blueprint('api', __name__)


def requires_login(f):
    @wraps(f)
    @orm.db_session
    def decorated_function(*args, **kwargs):
        if session.get("token"):
            return f(*args, **kwargs)
        else:
            return abort(403)
    return decorated_function


@apis.route('/', methods=["GET", "PUT"])
@orm.db_session
def render_index():
    '''
    Render Function of main page.

    Args:
        None

    Returns:
        Rendered HTML template of the SA.
        Status code: 200 / 500.
    '''
    try:
        if not session.get("token"):
            redirect_url = url_for("api.oauth2_callback", _external=True)
            print("url: ", redirect_url)
            print("redirect to oauth login page")
            ask_login = {"prompt": "login"}
            return oauth2_client.iottalk.authorize_redirect(redirect_url, **ask_login)
        user = CB_Account.get(account=session["user"])
        if None is user:
            raise NotFoundError
        return render_template("main.html", userLevel=user.privilege), 200
    except NotFoundError:
        api_logger.exception("Account recorded in session does not exist")
        abort(500)
    except Exception as err:
        api_logger.exception(err)
        abort(500)


@apis.route("/subsystem/infos", methods=["GET"])
@requires_login
def get_infos():
    return f'http://{env_config["IoTtalk"]["ServerIP"]}:7788/connection#', 200


@apis.route('/cb/<int:cb_id>/new_rules', methods=['POST'])
@requires_login
@orm.db_session
def set_rules(cb_id):
    '''
    Set the rules contained in the request sent from the specified CB.

    Args:
        cb_id: ID of the requester SA.
        request: A list of CBElements in json format.
            each CBElement will contain the following fields
                `rule_id`
                `actuator_alias`
                `mode`
                `sensor_index`
                `threshold_open`
                `threshold_close`
                `comparison_open`
                `comparison_close`
                `time_open`
                `time_close`
                `weekday`
                `duty_pos`
                `duty_neg`
            Refer to models.py for each field's meaning.

    Returns:
        Status code: 200 / 400 / 500
        msg: Depends on status code.
            200: "Configuration Saved".
            400: a string containing invalid actuators.
            500: "Internal Server Error".
    '''
    cb = CB[cb_id]
    api_logger.info(f'Start setting new rules of CB {cb.cb_name}')
    invalid_list = list()
    rules = request.json
    try:
        for rule_setting in rules:
            invalid = False
            # Sensor threshold setup < 0
            if rule_setting["mode"] == "Sensor":
                if rule_setting["comparison_open"] != "notset" and float(rule_setting["threshold_open"]) < 0.0:
                    invalid = True
                elif rule_setting["comparison_close"] != "notset" and float(rule_setting["threshold_close"]) < 0.0:
                    invalid = True
            # dutyPos > 0 but no dutyNeg
            if int(rule_setting["duty_pos"]) > 0:
                if rule_setting["duty_neg"] is None or int(rule_setting["duty_neg"]) <= 0:
                    invalid = True
            if invalid:
                invalid_list.append(rule_setting["actuator_alias"])

        if len(invalid_list):
            raise WrongSettingError

        api_logger.info('\tStart setting rules')
        accessible_users = [user.account for user in cb.account_set]
        title = f"ControlBoard {cb.cb_name} has CBElements changed by {session['user']}, detail as follows\n"

        for rule_setting in rules:
            actuator = rule_setting["actuator_alias"]
            rule_setting["weekday"] = ",".join([str(weekday) for weekday in rule_setting["weekday"]])
            if rule_setting["time_open"] is not None:
                time_open = datetime.time(
                    hour=rule_setting["time_open"][0],
                    minute=rule_setting["time_open"][1],
                    second=rule_setting["time_open"][2]
                )
                rule_setting["time_open"] = time_open

            if rule_setting["time_close"] is not None:
                time_close = datetime.time(
                    hour=rule_setting["time_close"][0],
                    minute=rule_setting["time_close"][1],
                    second=rule_setting["time_close"][2]
                )
                rule_setting["time_close"] = time_close

            rule = CBElement[rule_setting["rule_id"]]
            rule.set(**rule_setting)
            if rule_setting["mode"] == "Sensor":
                rule_setting["sensor_alias"] = rule.sensor_alias.split(',')[rule_setting["sensor_index"]]
        cb_db.commit()
        email_notifier.notify_user(title, rules, accessible_users)
        if cb_id in running_cb:
            status = deregister_ag(running_cb[cb_id].ag_token, api_logger)
            if not status:
                api_logger.exception("Error creating new rule, Change User configuraion failed, check API logs")
                return "Internal Server Error", 500
        cb_db.commit()

        status, ag_token = register_ag(cb, api_logger)
        if not status:
            api_logger.exception("Error creating new rule, Change User configuraion failed, check API logs")
            return "Internal Server Error", 500
        cb.ag_token = ag_token
        running_cb[cb.cb_id] = cb

        do_id = [int(id) for id in cb.do_id.split(',')]
        status = bind_device_ag(cb.mac_addr, cb.p_id, do_id, api_logger)
        if not status:
            api_logger.exception("Error creating new rule, Change User configuraion failed, check API logs")
            return "Internal Server Error", 500
        cb_db.commit()
        return 'Configuration Saved', 200
    except WrongSettingError:
        invalid_actuators = str()
        for actuator in invalid_list:
            invalid_actuators += (actuator + ' ')
        api_logger.exception(f"Invalid new rules of CB {cb.cb_name} detected, abort all")
        abort(400, f"Abnormal threshold setting of {invalid_actuators} detected, aborting all")
    except orm.RowNotFound:
        api_logger.exception("Specified rule not found")
        abort(400, "Specified CB not found")
    except orm.MultipleRowsFound:
        api_logger.exception("Multiple Rule found for the same actuator")
        abort(400, "Multiple Rules for the same actuator detected")
    except Exception as err:
        api_logger.exception(err)
        abort(500)


@apis.route('/cb/<int:cb_id>/rules', methods=['GET'])
@requires_login
@orm.db_session
def get_rules(cb_id):
    '''
    Get the rules contained in the specified CB.

    Args:
        cb_id: ID of the requester CB.

    Returns:
        Status code: 200 / 500.
        rule_list: A list containing rules of the specific CB. Each element of this list is a rule in dictionary format.
            Each rule will contain the following information
                `ruleID`: integer, primary key of the rule in database table `CBElement`.
                `actuator`: string, indicating user-defined actuator df-alias on IoTtalk GUI.
                `sensors`: list of strings, indicating user-defined sensor df-alias on IoTtalk GUI.
                `mode`: string, indicating manual on/off or sensor/timer.
                `content`: dictionary, the rule's content. including the following fields.
                    `openSensor`: string, should be one of bigger/smaller/null.
                    `openSensorVal`: integer, the threshold value to trigger the actuator.
                    `closeSensor`: string, should be one of bigger/smaller/null.
                    `closeSensorVal`: integer, the threshold value to close the actuator.
                    `openTimer`: list of length 3, represent the timing allowed to trigger the actuator.
                    `closeTimer`: list of length 3, represent the timing allowed to close the actuator.
                    `dutyPos`: integer, time in seconds representing the positive cycle length of one Duty cycle.
                    `dutyNeg`: integer, time in seconds representing the negative cycle length of one Duty cycle.
                    `weekdays`: list of integers representing weekdays. Mon <=> 0, Sun <=> 6, All <=> 7.

            The following 5 fields are dummy data for frontend rendering.
                `dirty`: False,
                `prevTrigger`: -10000,
                `status`: False,
                `time`: "00:00",
                `value`: 0
            `rule_list` will be empty if the specified CB is not running.
    '''
    rule_list = list()
    try:
        cb = CB[cb_id]
        for rule in cb.rule_set:
            content = dict()

            content["openTimer"] = [int(data) for data in rule.time_open.strftime('%H:%M:%S').split(":")]
            content["closeTimer"] = [int(data) for data in rule.time_close.strftime('%H:%M:%S').split(":")]
            content["openSensor"] = rule.comparison_open
            content["closeSensor"] = rule.comparison_close
            content["openSensorVal"] = rule.threshold_open
            content["closeSensorVal"] = rule.threshold_close
            content["dutyPos"] = rule.duty_pos
            content["dutyNeg"] = rule.duty_neg
            if len(rule.weekday):
                content["weekdays"] = rule.weekday.split(",")
            else:
                content["weekdays"] = list()

            tmp = {
                "ruleID": rule.rule_id,
                "actuator": rule.actuator_alias,
                "sensors": rule.sensor_alias.split(",") if len(rule.sensor_alias) else list(),
                "selectedSensor": rule.sensor_index,
                "mode": rule.mode,
                "content": content,
                "dirty": False,
                "prevTrigger": -10000,
                "status": False,
                "time": "00:00",
                "value": 0
            }
            rule_list.append(tmp)
        return jsonify(rule_list), 200
    except orm.core.ObjectNotFound:
        return jsonify([]), 200
    except Exception as err:
        api_logger.exception(err)
        abort(500, "Internal server error")


@apis.route('/cb/<int:cb_id>/current_data', methods=['GET'])
@requires_login
@orm.db_session
def get_datum(cb_id):
    '''
    Get the datum of sensors manipulated by the specified CB.

    Args:
        cb_id: ID of the requester CB.

    Returns:
        Status code: 200 / 500.
        res_dict: A json object containing the lastest data of each sensor and trigger status.
    '''
    res_dict = dict()
    try:
        cb = CB[cb_id]
        if int(cb_id) not in running_cb:
            raise NotFoundError
        rules = cb.rule_set

        for rule in rules:
            status = running_status[rule.rule_id]
            status["time"] = datetime.datetime.now().strftime("%H:%M")
            res_dict[rule.rule_id] = status
        return jsonify(res_dict), 200
    except NotFoundError:
        api_logger.warning(f"Specified CB ID {cb_id} not running")
        api_logger.warning("Current running cb:")
        api_logger.warning(running_cb)
        return "Specified CB not running", 200
    except Exception as err:
        api_logger.exception(err)
        api_logger.warning(f"Specified CB ID {cb_id} failed at getting data")
        api_logger.warning(running_status)
        abort(500, err)


@apis.route('/cb/refresh_cb/<int:cb_id>', methods=['GET'])
@requires_login
@orm.db_session
def refresh_cb(cb_id):
    '''
    Fetch NetworkApplications to read IDF/ODF name.

    Args:
        cb_id: ID of the cb to sync with IoTtalk Project.

    Returns:
        Status code: 200 / 400 / 500
        Msg: Corresponding execution result.
    '''
    try:
        cb = CB[cb_id]
        if use_v1:
            NAs = requests.post(  # Workaround for V1 CCM API project.get lacking NA info.
                f"http://{env_config['IoTtalk']['ServerIP']}:7788/reload_data",
                data={"p_id": cb.p_id}
            )
            NAs = json.loads(NAs.text)["join"]
        else:
            raise NotImplementedError
        print(NAs)
        if not len(NAs):
            raise NotFoundError
        # Create CBElements for each NA
        src, dst = dict(), dict()
        na_ids = list()
        for na in NAs:
            state, na_info = get_na_ag(cb.p_id, na[0], api_logger)
            if not state:
                raise CCMAPIFailError
            print("=============")
            print("na_info: ", na_info)
            print("=============")
            order, idfs, odfs = 0, list(), list()
            direction = 0  # 0 for src, 1 for dst
            for idf in na_info["input"]:
                if idf["df_name"].startswith("CBElement-TI"):
                    status, data = get_na_ag(cb.p_id, na[0], api_logger)
                    if not status:
                        api_logger.Exception("Get Na info failed")
                    set_fn_ag(cb.p_id, data, api_logger)
                    na_ids.append(na[0])
                    order = int(idf["df_name"].replace("CBElement-TI", ""))
                    direction = 1
                idfs.append([idf["df_name"], idf["alias_name"].replace("-TI", "")])

            for odf in na_info["output"]:
                if odf["df_name"].startswith("CBElement-O"):
                    na_ids.append(na[0])
                    order = int(odf["df_name"].replace("CBElement-O", ""))
                    direction = 0
                odfs.append([odf["df_name"], odf["alias_name"].replace("-O", "")])

            # Not a CB related NA.
            if 0 == order:
                continue
            if direction:
                dst[order] = odfs
            else:
                src[order] = idfs
        print(na_ids)
        nas = ",".join(str(na_id) for na_id in na_ids)
        cb.na_id = nas

        actuators = list()
        for order, actuator in dst.items():
            old_rule = CBElement.get(df_order=order, cb=cb)
            has_record = False
            if None is not old_rule:
                if old_rule.actuator_alias == actuator[0][1]:
                    has_record = True
                else:
                    old_rule.delete()
            actuators.append(actuator[0][1])
            if order not in src:  # Timer Type, No Sensors connected.
                if has_record:
                    old_rule.set(
                        actuator_alias=actuator[0][1],
                        actuator_df=actuator[0][0],
                        sensor_alias="",
                        mode="OFF",
                        df_order=order,
                    )
                else:
                    cb.rule_set.add(
                        CBElement(
                            **default_rules,
                            actuator_alias=actuator[0][1],
                            actuator_df=actuator[0][0],
                            df_order=order,
                            mode="OFF",
                            cb=cb
                        )
                    )
            else:  # Sensor type
                if has_record:
                    old_rule.set(
                        actuator_alias=actuator[0][1],
                        actuator_df=actuator[0][0],
                        sensor_alias=",".join([row[1] for row in src[order]]),
                        sensor_df=",".join([row[0] for row in src[order]]),
                        df_order=order,
                    )
                else:
                    cb.rule_set.add(
                        CBElement(
                            **default_rules,
                            actuator_alias=actuator[0][1],
                            actuator_df=actuator[0][0],
                            sensor_alias=",".join([row[1] for row in src[order]]),
                            sensor_df=",".join([row[0] for row in src[order]]),
                            df_order=order,
                            mode="OFF",
                            cb=cb
                        )
                    )
        cb_db.commit()
        for rule in cb.rule_set:
            if rule.actuator_alias not in actuators:
                cb.rule_set.remove(rule)
        cb.status = True

        if cb.ag_token != "NotCreated":
            status = deregister_ag(cb.ag_token, api_logger)
            if not status:
                api_logger.exception(f"Deregister CB {cb.cb_name} failed")
                abort(500, "Deregister AG CB failed, check api log and AG")

        # Register device
        status, ag_token = register_ag(cb, api_logger)
        if not status:
            cb.delete()
            cb_db.commit()
            abort(500, f"Create CB {cb.cb_name} failed at registering device, check api log and AG")
        cb.ag_token = ag_token

        # Bind device to DO
        time.sleep(1)  # Uncomment this if the IoTtalk Server cannot create DO in time.
        do_id = cb.do_id.split(",")
        status, dm_name = bind_device_ag(cb.mac_addr, cb.p_id, do_id, api_logger)
        if not status:
            deregister_ag(cb.ag_token, api_logger)
            cb.delete()
            cb_db.commit()
            abort(400, f"Create CB {cb.cb_name} failed at auto binding, check api log files")
        running_cb[cb.cb_id] = cb
        for rule in cb.rule_set:
            if rule.rule_id not in running_status:
                running_status[rule.rule_id] = default_status
        cb_db.commit()
        api_logger.info(f"Create New CB, DM Name: {dm_name}")

        title = f"ControlBoard {cb.cb_name} is refreshed by {session['user']}, new CBElements as follows\n"
        rules = [rule.to_dict() for rule in cb.rule_set]
        users = [user.account for user in cb.account_set]
        email_notifier.notify_user(title, rules, users)
        return f"Create New CB, DM Name: {dm_name}", 200
    except NotFoundError:
        api_logger.warning("No NAs found, remind user to create NAs")
        cb = CB[cb_id]
        abort(400, "No NA detected, please create Join point in Project {cb.cb_name}")
    except CCMAPIFailError:
        api.logger.exception("CCMAPI failed, check which part of the procedure fails")
        abort(500, "Internal Server Error")
    except Exception as err:
        api_logger.exception(err)
        abort(500, "Internal Server Error")


@apis.route('/cb/disable_cb/<int:cb_id>', methods=['PUT'])
@requires_login
@orm.db_session
def disable_cb(cb_id):
    '''
    Set specified CB's status to false, indicating it's in maintanance.

    Args:
        cb_id: ID of the specified CB

    Returns:
        None
    '''
    try:
        CB[cb_id].status = not CB[cb_id].status
        return "Set Maintanance done", 200
    except Exception as err:
        api_logger.exception(err)
        abort(500)


@apis.route('/cb/create_cb', methods=['POST'])
@requires_login
@orm.db_session
def create_cb():
    '''
    Creates an empty CB. Further steps are to be triggered by refresh_CB event after
        User has setup GUI connections(NAs).
    Args:
        new_cb: Name of this CB given by the user.

    Returns:
        Status code: 200 / 400 / 500.
        msg: Corresponding execution result.
    '''
    new_cb = request.get_data().decode("utf-8")
    mac_addr = str(uuid.uuid4())

    cb = CB(cb_name=new_cb, ag_token="NotCreated", mac_addr=mac_addr,
            p_id=-1, do_id="-1", status=False, na_id="-1", dedicated=True)

    cb_db.commit()
    api_logger.info("Start Creating CB")

    try:
        new_project = True
        # Create Project
        status, p_id = create_proj_ag(new_cb, api_logger)
        if not status:  # Project already exists
            new_project = False
            cb.dedicated = False
        status, project_info = get_proj_ag(new_cb, api_logger)
        if not status:
            cb.delete()
            cb_db.commit()
            abort(400, "Create CB failed at getting project information")
        cb.p_id = project_info["p_id"]
        p_id = project_info["p_id"]

        do_id = list()
        if not new_project:  # Check if the DM of ControlBoard exists in the assigned project
            if use_v1:
                for do in project_info["ido"]:
                    if do["dm_name"] == "ControlBoard":
                        do_id.append(do["do_id"])
                for do in project_info["odo"]:
                    if do["dm_name"] == "ControlBoard":
                        do_id.append(do["do_id"])
        if len(do_id) != 2:
            # Create Device Object
            status, do_id = create_do_ag(p_id, iottalk_info["df_id"], "ControlBoard", api_logger)
            if not status:
                cb.delete()
                cb_db.commit()
                abort(500, "Create CB failed at creating DO, check api log files and IoTtalk CCM.")

        status, project_info = get_proj_ag(new_cb, api_logger)
        # Fetch dfo ids
        dfo_ids = list()
        for ido in project_info["ido"]:
            if ido["dm_name"] == "ControlBoard":
                cb_idf = ido["dfo"]
                cb_ido = ido["do_id"]
                break
        for odo in project_info["odo"]:
            if odo["dm_name"] == "ControlBoard":
                cb_odf = odo["dfo"]
                cb_odo = odo["do_id"]
                break
        for idf, odf in zip(cb_idf, cb_odf):
            dfo_ids.append([(cb_ido, idf["df_id"]), (cb_odo, odf["df_id"])])
        for i, dfo_pair in enumerate(dfo_ids):
            state, res = create_na_ag(p_id, f"test{i}", i, dfo_pair, api_logger)

        if use_v1:
            cb.do_id = str(do_id[0]) + ',' + str(do_id[1])
        else:
            cb.do_id = str(do_id)
        account = CB_Account.get(account=session["user"])
        account.cb_set.add(cb)
        cb.account_set.add(account)

    except NotImplementedError:
        api_logger.exception("IoTtalk V2 is not supported")
        return "IoTtalk V2 is not supported", 400
    except Exception as err:
        api_logger.exception(err)
        if -1 is not cb.p_id:
            delete_proj_ag(cb.p_id, api_logger)
        cb.delete()
        return "Internal server error", 500

    cb_db.commit()
    return "Create SA succeeded", 200


@apis.route('/cb/delete_cb', methods=['POST'])
@requires_login
@orm.db_session
def delete_cb(cb_id=None):
    '''
    Delete CB with specified cb_id.

    Args:
        cb_id: ID of the requester CB.

    Returns:
        Status code: 200 / 400 / 500
        message: 'CB deleted successfully'.
    '''
    if None is cb_id:
        cb_id = int(request.get_data().decode("utf-8"))
    cb = CB[cb_id]
    try:
        if use_v1:
            for do_id in cb.do_id.split(","):
                status = delete_do_ag(cb.p_id, int(do_id), api_logger)
        if not status:
            api_logger.exception(f"Error delete CB {cb.cb_name}, Delete DO failed, check api log file")
            return "Delete CB failed, check api log files", 500

        na_ids = cb.na_id.split(",")
        if na_ids[0] != "-1":
            for na_id in na_ids:
                status, res = delete_na_ag(int(na_id), cb.p_id, api_logger)
                if not status:
                    api_logger.exception(f"Error delete CB {cb.cb_name}, Delete NA {res} failed, check api log file")
                    return "Delete CB failed, check api log files", 500

        if cb.ag_token != "NotCreated":
            status = deregister_ag(cb.ag_token, api_logger)
            if not status:
                api_logger.exception(f"Error delete CB {cb.cb_name}, Deregister SA failed, check api log file")
                return "Delete CB failed, check api log files", 500
        if cb.dedicated:
            status, res = delete_proj_ag(cb.p_id, api_logger)
            if not status:
                api_logger.exception(f"Error delete Project {cb.cb_name}, Reason: {res} , check api log file")
                return "Delete CB failed, check api log files", 500
        cb.delete()
        if cb_id in running_cb:
            del running_cb[cb_id]
        api_logger.info(f"Delete Running CB {cb.cb_name}")
        cb_db.commit()
        return "Delete CB succeed", 200
    except KeyError:
        api_logger.exception(f'Specified Field {cb.cb_name} not running')
        return "Specified SA not found", 400
    except Exception as err:
        api_logger.exception(err)
        abort(500)


@apis.route('/cb/get_cb/<string:usr_account>', methods=['GET'])
@requires_login
@orm.db_session
def get_cb(usr_account):
    '''
    Returns a list containing all accessible ControlBoards of the specified user given user account

    Args:
        usr_account: Account of the requester user.

    Returns:
        Status code: 200 / 401 / 403
        accessible_cb: A Dict containing 2 lists
            accessibleProjects: A list containing all `CB_id`s owned/shared to this user.
            optionProjects: A list of CBs including all CBs shared to this user.

            If user is not a admin user, that `accessibleProjects` will be exactly the same as `optionProjects`.
            Otherwise `optionProjects` would contains all CBs.
    '''
    try:
        print(usr_account)
        if "self" == usr_account:  # Access current logined user's accessible CBs.
            usr_account = session["user"]
        current_user = CB_Account.get(account=session["user"])
        if 0 == current_user.privilege and usr_account != session["user"]:
            raise NotAuthorizedError
        accessible_cb = list()
        if "all" == usr_account:
            for cb in CB.select()[:]:
                accessible_cb.append({
                    "value": cb.cb_id,
                    "text": cb.cb_name,
                    "status": cb.status
                })
        else:
            account = CB_Account.get(account=usr_account)
            if None is account:
                raise NotFoundError
            for cb in account.cb_set:
                accessible_cb.append({
                    "value": cb.cb_id,
                    "text": cb.cb_name,
                    "status": cb.status
                })
        return jsonify(accessible_cb), 200
    except NotAuthorizedError:
        api_logger.exception("Error Getting ControlBoard, Permission denied.")
        # TODO: redirect to AAA login page.
        abort(403, "Permission denied")
    except NotFoundError:
        api_logger.exception("No such user")
        abort(401, "No such user")
    except Exception as err:
        api_logger.exception(err)
        abort(500, err)


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
            api_logger.exception('An error encountered when handling login, check the follow logs')
            api_logger.exception(err)
    else:
        return "AAA login failed", 400

    session['username'] = account
    session['']

    return 'hello', 200


@apis.route("/account/get_accounts", methods=['GET'])
@requires_login
@orm.db_session
def get_users():
    '''
    Returns all users, the logined user must be privileged to call this entry.

    Args:
        None

    Returns:
        Status code: 200 / 401 / 403 / 500.
        users: A list of dictionary, each dict contains two keys `superuser` and `username`.
    '''
    try:
        current_user = CB_Account.get(account=session["user"])
        if None is current_user:
            raise NotFoundError
        if not current_user.privilege:
            raise NotAuthorizedError
        users = list()
        for account in CB_Account.select():
            users.append({
                "superuser": account.privilege,
                "username": account.user_name,
                "email": account.account
            })
        return jsonify(users), 200
    except NotFoundError:
        api_logger.exception("No such user")
        abort(401, "No such user")
    except NotAuthorizedError:
        api_logger.exception("User not authorized to access this api")
        abort(403, "User not authorized")
    except Exception as err:
        api_logger.exception(err)
        abort(500, err)


@apis.route('/account/adjust_privilege/<string:usr_name>', methods=['POST'])
@requires_login
@orm.db_session
def adjust_privilege(usr_name):
    '''
    Adjust user privilege and accessible CBs

    Args:
        usr_name: String, account of the specified user.
        usr_profile: Dictionary containing two fields `privilege` and `accessible_cb`
            privilege: Int, 0 or 1, indicating user/admin individually.
            accessible_cb: List, cb_ids this user is granted to access.

    Returns:
        Status code: 200 / 401 / 403 / 500
        Msg: Corresponding execution result.
    '''
    try:
        data = request.json
        current_user = CB_Account.get(account=session["user"])
        if current_user.privilege == 0:
            raise NotAuthorizedError
        account = CB_Account.get(account=usr_name)
        if None is account:
            raise NotFoundError
        account.privilege = data["privilege"]
        account.cb_set.clear()
        for cb_id in data["accessible_cb"]:
            account.cb_set.add(CB[cb_id])
            CB[cb_id].account_set.add(account)
        cb_db.commit()
        return "setup done", 200
    except NotFoundError:
        api_logger.exception("No Such User")
        abort(401, "No Such User")
    except NotAuthorizedError:
        abort(403, "Permission denied")
    except Exception as err:
        api_logger.exception(err)
        abort(500)


@apis.route('/account/oauth_callback', methods=['GET'])
@orm.db_session
def oauth2_callback():
    '''
    CallBack route for OAuth2.0, This route will be invoked when user successfully logined from the OAuth Server.

    Args:
        None.

    Returns:
        Rendered HTML template of the SA.
        Status code: 302 / 500.
    '''
    print("enter oauth callback")
    if not request.args.get("code"):
        if session.get("token"):
            print("user already logined in")
            return redirect(url_for("/"))

        redirect_url = url_for('api.oauth2_callback', _external=True)
        return oauth2_client.iottalk.authorize_redirect(redirect_url)

    try:
        # Exchange access token with an authorization code with token endpoint
        #
        # Ref: https://docs.authlib.org/en/stable/client/frameworks.html#id1
        token_response = oauth2_client.iottalk.authorize_access_token()

        # Parse the received ID token
        user_info = oauth2_client.iottalk.parse_id_token(token_response)
        print(user_info)
    except Exception as err:
        api_logger.exception(err)
        abort(500)

    try:
        user = CB_Account.get(account=user_info["email"])

        if None is user:  # Create a new account
            num_accounts = CB_Account.select().count()
            print("create new account")
            user = CB_Account(
                account=user_info["email"],
                privilege=1 if num_accounts == 0 else 0,
                access_token=token_response["access_token"],
                user_name=user_info["preferred_username"]
            )
        print("write cookie")
        session["token"] = token_response["access_token"]
        session["user"] = user.account
        user.access_token = token_response["access_token"]

        return redirect(url_for("api.render_index"))
    except Exception as err:
        api_logger.exception(err)
        abort(500)


@apis.route('/account/logout', methods=['PUT'])
@orm.db_session
def logout():
    '''
    Logout current user by deleting session and redirect to Account System's login page.

    Args:
        None

    Returns:
        message indicating logout successfully
    '''
    user = CB_Account.get(account=session["user"])
    user.access_token = "empty"

    session.pop("user")
    session.pop("token")

    return "logout successfully", 200
