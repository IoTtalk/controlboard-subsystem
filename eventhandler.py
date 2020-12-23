import datetime
import json
import requests
import time
import os
import uuid


from flask import abort
from flask import Blueprint
from flask import jsonify
from flask import render_template
from flask import request
from flask import session
from flask import redirect
from werkzeug.utils import secure_filename
from pony import orm


from utils import running_sa, running_status
from utils import make_logger
from utils import create_proj_ag, delete_proj_ag
from utils import create_do_ag
from utils import register_ag, deregister_ag, bind_device_ag, get_na_ag
from models import cb_db
from models import UserRule, CB_Account, CB_SA, CB
from config import default_rules
from config import env_config
from config import icon_extensions
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
    return render_template("main.html"), 200


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
            api_logger.exception("Error creating new rule, Multiple Rules for the same mapping found")
            return "Internal Server Error", 502

    if sa_id in running_sa:
        status = deregister_ag(running_sa[sa_id], api_logger)
        if not status:
            api_logger.exception("Error creating new rule, Change User configuraion failed, check API logs")
            return "Internal Server Error", 502

    status, ag_token = register_ag(sa, api_logger)
    if not status:
        api_logger.exception("Error creating new rule, Change User configuraion failed, check API logs")
        return "Internal Server Error", 502
    sa.ag_token = ag_token
    running_sa[sa.sa_id] = sa

    do_id = [int(id) for id in sa.do_id.split(',')]
    status = bind_device_ag(sa.mac_addr, sa.p_id, do_id, api_logger)

    if not status:
        api_logger.exception("Error creating new rule, Change User configuraion failed, check API logs")
        return "Internal Server Error", 502

    return 'Configuration Saved', 200


@apis.route('/sa/<int:sa_id>/stop', methods=['GET'])
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


@apis.route('/sa/<int:sa_id>/rules', methods=['GET'])
@orm.db_session
def get_rules(sa_id):
    '''
    Get the rules contained in the specified SA.

    Args:
        sa_id: ID of the requester SA.

    Returns:
        Status code: 200 / 400.
        rule_list: A list containing rules of the specific SA. Each element of this list is a rule in dictionary format.
            Each rule will contain the following information
                `ruleID`: integer, primary key of the rule in database table `UserRule`.
                `actuator`: string, indicating user-defined df-alias on IoTtalk GUI.
                `sensors`: list of strings, indicating user-defined df-alias on IoTtalk GUI.
                `mode`: string, indicating manual on/off or sensor/timer.
                `content`: dictionary, the rule's content. including the following fields.
                    `openSensor`: string, should be one of bigger/smaller/null.
                    `openSensorVal`: integer, the threshold value to trigger the actuator.
                    `closeSensor`: string, should be one of bigger/smaller/null.
                    `closeSensorVal`: integer, the threshold value to close the actuator.
                    `openTimer`: datetime string, represent the timing allowed to trigger the actuator.
                    `closeTimer`: datetime string, represent the timing allowed to close the actuator.
                    `dutyPos`: integer, time in seconds representing the positive cycle length of one Duty cycle.
                    `dutyNeg`: integer, time in seconds representing the negative cycle length of one Duty cycle.
                    `weekdays`: list of integers representing weekdays. Mon <=> 0, Sun <=> 6, All <=> 7.
    '''
    res_list = list()
    try:
        if sa_id not in running_sa:
            raise KeyError
        sa = CB_SA[sa_id]
        for rule in sa.rule_set:
            content = dict()

            content["openTimer"] = [int(data) for data in rule.time_open.strftime('%H:%M:%S').split(":")]
            content["closeTimer"] = [int(data) for data in rule.time_close.strftime('%H:%M:%S').split(":")]
            content["openSensor"] = rule.comparison_open
            content["closeSensor"] = rule.comparison_close
            content["dutyPos"] = rule.duty_pos
            content["dutyNeg"] = rule.duty_neg
            if len(rule.weekday):
                content["weekdays"] = rule.weekday.spilt(",")
            else:
                content["weekdays"] = list()

            tmp = {
                "ruleID": rule.rule_id,
                "actuator": rule.actuator_alias,
                "sensors": rule.sensor_alias.split(",") if len(rule.sensor_alias) else list(),
                "mode": rule.mode,
                "content": content
            }
            res_list.append(tmp)
        return jsonify(res_list), 200
    except KeyError:
        api_logger.exception("Specified SA not running")
        return abort(400, "Specified SA not running")
    except Exception as err:
        api_logger.exception(err)
        return abort(500, "Internal server error")


@apis.route('/sa/<sa_id>current_data', methods=['POST'])
@orm.db_session
def set_datum(sa_id):
    pass


@apis.route('/sa/<int:sa_id>/current_data', methods=['GET'])
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
        if int(sa_id) not in running_sa:
            raise KeyError
        rules = CB_SA[sa_id].rule_set
    except KeyError:
        api_logger.exception("Error getting SA's current data, Specified SA not running")
        return "Specified SA not running", 400

    for rule in rules:
        stats = running_status[rule.rule_id]
        stats["time"] = datetime.datetime.now().strftime("%H:%M")
        res_dict[rule.rule_id] = stats

    return jsonify(res_dict), 200


@apis.route('/subsystem/refresh_sa/<int:sa_id>', methods=['GET'])
def refresh_sa(sa_id):
    '''
    Fetch NetworkApplications to read IDF/ODF name.

    Args:
        sa_id: ID of the SA to get p_id.

    Returns:
        Status code: 200 / 400 / 502
        Msg: Corresponding execution result.
    '''
    try:
        with orm.db_session():
            sa = CB_SA[sa_id]
            if use_v1:
                NAs = requests.post(  # Workaround for V1 CCM API project.get lacking NA info.
                    f"http://{env_config['IoTtalk']['ServerIP']}:7788/reload_data",
                    data={"p_id": sa.p_id}
                )
                NAs = json.loads(NAs.text)["join"]
            else:
                NAs = ["testV2"]
            print(NAs)
            if not len(NAs):
                raise ValueError
            if len(sa.rule_set):
                sa.rule_set.clear()
            # Create UserRules for each NA
            src, dst = dict(), dict()
            for na in NAs:
                na_info = get_na_ag(sa.p_id, na[0], api_logger)[1]
                print("na_info: ", na_info)
                order, idfs, odfs = 0, list(), list()
                direction = 0  # 0 for src, 1 for dst
                for idf in na_info["input"]:
                    if idf["df_name"].startswith("Trigger-I"):
                        order = int(idf["df_name"][-1])
                        direction = 1
                    idfs.append([idf["df_name"], idf["alias_name"].replace("-I", "")])

                for odf in na_info["output"]:
                    if odf["df_name"].startswith("Threshold-O"):
                        order = int(odf["df_name"][-1])
                        direction = 0
                    odfs.append([odf["df_name"], odf["alias_name"].replace("-O", "")])

                # Not a CB related NA.
                if 0 == order:
                    continue
                if direction:
                    dst[order] = odfs
                else:
                    src[order] = idfs
            for order, actuator in dst.items():
                if order not in src:
                    sa.rule_set.add(
                        UserRule(
                            **default_rules,
                            actuator_alias=actuator[0][1],
                            actuator_df=actuator[0][0],
                            mode="Timer",
                            df_order=order,
                            sa=sa
                        )
                    )
                else:
                    print(src[order])
                    sa.rule_set.add(
                        UserRule(
                            **default_rules,
                            actuator_alias=actuator[0][1],
                            actuator_df=actuator[0][0],
                            sensor_alias=",".join([row[1] for row in src[order]]),
                            sensor_df=",".join([row[0] for row in src[order]]),
                            sensor_index=0,
                            df_order=order,
                            mode="Sensor",
                            sa=sa
                        )
                    )
            cb_db.commit()

            if sa.ag_token != "NotCreated":
                status = deregister_ag(sa, api_logger)
                if not status:
                    api_logger.exception("Deregister Sa failed")
                    abort(500, "Deregister SA failed")

            # Register device
            status, ag_token = register_ag(sa, api_logger)
            if not status:
                sa.delete()
                abort(400, "Create SA failed at registering device, check api log files")
            sa.ag_token = ag_token

            # Bind device to DO
            time.sleep(5)  # Uncomment this if the IoTtalk Server cannot create DO in time.
            do_id = sa.do_id.split(",")
            status, dm_name = bind_device_ag(sa.mac_addr, sa.p_id, do_id, api_logger)
            if not status:
                deregister_ag(sa, api_logger)
                sa.delete()
                abort(400, "Create SA failed at auto binding, check api log files")
            running_sa[sa.sa_id] = sa

            api_logger.info(f"Create New SA, DM Name: {dm_name}")
            return f"Create New SA, DM Name: {dm_name}", 200
    except ValueError:
        api_logger.exception("No NAs found, remind user to create NAs")
        return abort(400, f"No NAs detected, please create Join point in Project {str(sa_id) + '-' + sa.sa_name}")
    except Exception as err:
        api_logger.exception(err)
        return abort(502, "Internal Server Error")


@apis.route('/subsystem/create_sa', methods=['POST'])
def create_sa():
    '''
    Creates an empty SA.

    Args:
        cb_id: The ControlBoard this new SA belongs to.
        sa_name: Name of this SA given by the user.

    Returns:
        Status code: 200 / 400.
        proj_name: Project name for user to choose input sensors and output actuators.
    '''
    sa_spec = request.json
    with orm.db_session():
        if not CB.exists(cb_id=sa_spec["cb_id"]):
            abort(400, "Specified ControlBoard not existed")
        mac_addr = str(uuid.uuid4())
        sa = CB_SA(sa_name=sa_spec["sa"]["text"], ag_token="NotCreated", mac_addr=mac_addr,
                   p_id=-1, do_id="-1", pinned=sa_spec["sa"]["pinned"], cb=CB[sa_spec["cb_id"]])
        cb_db.commit()
        api_logger.info("Start Creating CB SA")

        # Create Project
        status, p_id = create_proj_ag(sa, api_logger)
        if not status:
            deregister_ag(sa, api_logger)
            sa.delete()
            abort(400, "Create SA failed at creating project, check api log files")
        sa.p_id = p_id

        # Create Device Object
        status, do_id = create_do_ag(p_id, api_logger)
        if not status:
            deregister_ag(sa, api_logger)
            sa.delete()
            abort(400, "Create SA failed at creating DO, check api log files")
        if use_v1:
            sa.do_id = str(do_id[0]) + ',' + str(do_id[1])
        else:
            sa.do_id = str(do_id)
    return "Create SA succeeded", 200


@apis.route('/subsystem/delete_sa', methods=['POST'])
@orm.db_session
def delete_sa():
    '''
    Delete SA with specified sa_id.

    Args:
        sa_id: ID of the requester SA.

    Returns:
        Status code: 200.
        message: 'SA deleted successfully'.
    '''
    try:
        sa_id = int(request.get_data().decode("utf-8"))
        sa = CB_SA[sa_id]
        if sa.ag_token != "NotCreated":
            status = deregister_ag(sa, api_logger)
            if not status:
                api_logger.exception("Error delete SA, Deregister SA failed, check api log file")
                return "Delete SA failed, check api log files", 502
        sa.delete()
        status, message = delete_proj_ag(sa.p_id, api_logger)
        if not status:
            api_logger.exception("Error delete SA, Delete project failed, check api log file")
            api_logger.exception(f"Error msg from AG: {message}")
            return "Delete SA failed, check api log files", 502

        api_logger.info(f"Delete Running SA, SA_ID: {sa.sa_id}")
        return "Delete SA succeed", 200
    except KeyError:
        api_logger.exception('Specified ControlBoard not running')
        return "Specified SA not found", 400


@apis.route('/subsystem/get_sa/<int:cb_id>', methods=['GET'])
def get_sa(cb_id):
    '''
    Get accessible sa_ids and sa_names of the specified user. Called when rendering SAs available to the user.

    Args:
        cb_id: The ID of the requested CB.

    Returns:
        Status code: 200 / 401 / 403
        available_sa: A list of CB SAs, each element is composed of sa_id and sa_name of the corresponging SA.
    '''
    available_sa = list()
    try:
        with orm.db_session():
            account = CB_Account.get(account=logined_user[session["token"]])
            if CB[cb_id] not in account.cb_set:
                raise ValueError
            for sa in CB[cb_id].sa_set:
                available_sa.append({
                    "text": sa.sa_name,
                    "value": sa.sa_id,
                    "pin": sa.pinned
                })
        return jsonify(available_sa), 200
    except KeyError:
        api_logger.exception("Error getting SA, User not logined!")
        abort(401, "Non-existed User!")
    except ValueError:
        api_logger.exception("Error getting SA, Requested CB is not shared with this user.")
        abort(403, "Not a superuser!")


@apis.route('/subsystem/cb_icon/<int:cb_id>', methods=["PUT"])
def manage_icon(cb_id):
    '''
    Change specified CB's icon client given `cb_id` and `file` from request.

    Args:
        cb_id: Specified CB's unique id.
        file: Image body to change.

    Returns:
        Status code: 200 / 400 / 401 / 403 / 502
        Message: Corresponding execution result.
    '''
    print(icon_extensions)
    try:
        with orm.db_session():
            account = CB_Account.get(account=logined_user[session["token"]])
            if not account.privilege:
                raise ValueError
            icon = request.files["file"]
            icon_name = secure_filename(icon.filename).rsplit(".", 1)
            if "." in icon.filename and icon_name[1] in icon_extensions:
                print(icon_name)
                icon_path = str(cb_id) + "_" + icon_name[0] + "." + icon_name[1]
                old_path = CB[cb_id].icon
                if old_path != env_config["env"]["default_icon"]:
                    os.remove(os.path.join(os.path.normpath(env_config["env"]["icon_path"]), old_path))
                CB[cb_id].icon = icon_path
                icon_path = os.path.join(env_config["env"]["icon_path"], icon_path)
                icon.save(icon_path)
            else:
                raise TypeError
            return "Icon change finished", 200
    except KeyError:
        api_logger.exception("Error Changing Icon, User not logined!")
        abort(401, "Non-existed User!")
    except ValueError:
        api_logger.exception("Error Changing Icon, User is not a superuser.")
        abort(403, "Not a superuser!")
    except TypeError:
        api_logger.exception("Error Changing Icon, Unsupported Icon extensions.")
        abort(400, "Non-supported icon format")
    except Exception as err:
        api_logger.exception("Unknown Error in Changing Icon.")
        api_logger.exception(err)
        abort(502, "Internal Server Error")


@apis.route('/subsystem/create_cb', methods=['POST'])
def create_cb():
    '''
    Create a Empty ControlBoard that contains no SA Field.

    Args:
        text: cb_name of this ControlBoard.
        shared: Whether to be seen by other users.

    Returns:
        Status Code: 200 / 400 / 401 / 500.
        Message: Corresponding execution result.
    '''
    new_cb = request.json
    try:
        with orm.db_session():
            owner = CB_Account.get(account=logined_user[session["token"]])
            cb = CB(
                cb_name=new_cb["text"],
                shared=new_cb["shared"],
                icon=env_config["env"]["default_icon"]
            )
            if None is owner:
                raise ValueError
            cb.account_set.add(owner)
        api_logger.info(f"Create ControlBoard by User {owner.account}, CB ID:  {cb.cb_id}")
    except KeyError:
        api_logger.exception("Error Create CB, User not logined")
        abort(401, "User not logined")
    except ValueError:
        api_logger.exception("Error Create CB, Non-existed User!")
        abort(400, "Non-existed User!")
    except Exception as err:
        api_logger.exception(err)
        abort(502, "Unknown Error occurred, contact subsystem-admin to check error log!")
    return "Success", 200


@apis.route('/subsystem/delete_cb', methods=['POST'])
def delete_cb():
    '''
    Delete CB and corresponding SAs / UserRules with specified cb_id.

    Args:
        cb_id: ID of the specified retrived from function `get_cb`

    Returns:
        Status Code: 200 / 403 / 500.
        Message: Corresponding execution result.
    '''
    try:
        cb_id = request.get_data().decode("utf-8")
        with orm.db_session():
            account = CB_Account.get(account=logined_user[session["token"]])
            api_logger.info(f"Delete ControlBoard {cb_id} by User {account.account}")
            if not account.privilege:
                raise ValueError
            if CB[cb_id].icon != env_config["env"]["default_icon"]:
                os.remove(os.path.join(os.path.normpath(env_config["env"]["icon_path"]), CB[cb_id].icon))
            CB[cb_id].delete()  # By applying cascade deleting.
        return "Specified ControlBoard deleted."
    except KeyError:
        api_logger.exception("Error Deleting ControlBoard, User not logined.")
        # TODO: redirect to AAA login page.
        abort(403, "Please login first")
    except ValueError:
        api_logger.exception("Error Deleting ControlBoard, User is not a superuser.")
        abort(403, "Not a superuser!")
    except Exception as err:
        api_logger.exception("Unknown error occurred, error message as belows")
        api_logger.exception(err)
        abort(502, "Internal error occurred")


@apis.route('/subsystem/get_cb', methods=['GET'])
def get_cb():
    '''
    Returns all accessible CB list of current logined user

    Args: None

    Returns:
        Status code: 200 / 401 / 403
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
                icon_path = os.path.join(os.path.normpath(env_config["env"]["icon_path"]), cb.icon)
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
        api_logger.exception("Error Getting ControlBoard, User not logined.")
        # TODO: redirect to AAA login page.
        abort(403, "Please Login first")
    except ValueError:
        api_logger.exception("Error Getting ControlBoard, No such user.")
        # TODO: redirect to AAA login page.
        abort(401, "No such User")


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
