import datetime
from functools import wraps
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


from exceptions import NotAuthorizedError, NotFoundError, WrongSettingError
from utils import running_sa, running_status
from utils import make_logger
from utils import create_proj_ag, delete_proj_ag
from utils import create_do_ag
from utils import register_ag, deregister_ag, bind_device_ag, get_na_ag
from models import cb_db
from models import UserRule, CB_Account, CB_SA, CB
from config import default_rules, default_status
from config import env_config
from config import icon_extensions
from config import use_v1


api_logger = make_logger('API', 'API')
apis = Blueprint('api', __name__)


def requires_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("token"):
            return f(*args, **kwargs)
        else:
            # next_url = request.path
            # TODO: redirect to AAA to login
            session["token"] = str(uuid.uuid4())  # dummy token, should be replaced with AAA token
            session["user"] = "yb"  # dummy account
            return redirect("/")
    return decorated_function


@apis.route('/', methods=["GET"])
@requires_login
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
        print(session["user"])
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


@apis.route('/sa/<int:sa_id>/new_rules', methods=['POST'])
@requires_login
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
    try:
        for rule_setting in request.json:
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
        sa = CB_SA[sa_id]
        for rule_setting in request.json:
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

            rule = UserRule.get(sa=sa, actuator_alias=actuator)
            rule.set(**rule_setting)

        if sa_id in running_sa:
            status = deregister_ag(running_sa[sa_id], api_logger)
            if not status:
                api_logger.exception("Error creating new rule, Change User configuraion failed, check API logs")
                return "Internal Server Error", 500

        status, ag_token = register_ag(sa, api_logger)
        if not status:
            api_logger.exception("Error creating new rule, Change User configuraion failed, check API logs")
            return "Internal Server Error", 500
        sa.ag_token = ag_token
        running_sa[sa.sa_id] = sa

        do_id = [int(id) for id in sa.do_id.split(',')]
        status = bind_device_ag(sa.mac_addr, sa.p_id, do_id, api_logger)

        if not status:
            api_logger.exception("Error creating new rule, Change User configuraion failed, check API logs")
            return "Internal Server Error", 502

        return 'Configuration Saved', 200
    except WrongSettingError:
        invalid_actuators = str()
        for actuator in invalid_list:
            invalid_actuators += (actuator + ' ')
        api_logger.exception(f"Invalid new rules of SA NO. {sa_id} detected, abort all")
        abort(400, f"Abnormal threshold setting of {invalid_actuators} detected, aborting all")
    except orm.RowNotFound:
        api_logger.exception("Specified rule not found")
        abort(400)
    except orm.MultipleRowsFound:
        api_logger.exception("Multiple Rule found for the same actuator")
        abort(500)
    except Exception as err:
        api_logger.exception(err)
        abort(500)


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
@requires_login
@orm.db_session
def get_rules(sa_id):
    '''
    Get the rules contained in the specified SA.

    Args:
        sa_id: ID of the requester SA.

    Returns:
        Status code: 200 / 500.
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

            The following 5 fields are dummy data for frontend rendering.
                `dirty`: False,
                `prevTrigger`: -10000,
                `status`: False,
                `time`: "00:00",
                `value`: 0
            `rule_list` will be empty if the specified SA is not running.
    '''
    rule_list = list()
    try:
        if sa_id not in running_sa:
            raise NotFoundError
        sa = CB_SA[sa_id]
        for rule in sa.rule_set:
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
    except NotFoundError:
        api_logger.warning("Specified SA not running")
        return jsonify(list()), 200
    except Exception as err:
        api_logger.exception(err)
        return abort(500, "Internal server error")


@apis.route('/sa/<int:sa_id>/current_data', methods=['GET'])
@requires_login
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
            raise NotFoundError
        rules = CB_SA[sa_id].rule_set

        for rule in rules:
            status = running_status[rule.rule_id]
            status["time"] = datetime.datetime.now().strftime("%H:%M")
            res_dict[rule.rule_id] = status
    except NotFoundError:
        api_logger.exception("Error getting SA's current data, Specified SA not running")
        return "Specified SA not running", 400
    except Exception as err:
        api_logger.exception(err)
        return abort(500, err)

    return jsonify(res_dict), 200


@apis.route('/subsystem/refresh_sa/<int:sa_id>', methods=['GET'])
@requires_login
@orm.db_session
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
            raise NotFoundError
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
        actuators = list()
        for order, actuator in dst.items():
            old_rule = UserRule.get(df_order=order, sa=sa_id)
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
                        df_order=order,
                        mode="Timer",
                    )
                else:
                    sa.rule_set.add(
                        UserRule(
                            **default_rules,
                            actuator_alias=actuator[0][1],
                            actuator_df=actuator[0][0],
                            df_order=order,
                            mode="Timer",
                            sa=sa
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
                        mode="Sensor",
                    )
                else:
                    sa.rule_set.add(
                        UserRule(
                            **default_rules,
                            actuator_alias=actuator[0][1],
                            actuator_df=actuator[0][0],
                            sensor_alias=",".join([row[1] for row in src[order]]),
                            sensor_df=",".join([row[0] for row in src[order]]),
                            df_order=order,
                            mode="Sensor",
                            sa=sa
                        )
                    )
        cb_db.commit()
        for rule in sa.rule_set:
            if rule.actuator_alias not in actuators:
                sa.rule_set.remove(rule)

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
        for rule in sa.rule_set:
            running_status[rule.rule_id] = default_status

        api_logger.info(f"Create New SA, DM Name: {dm_name}")
        return f"Create New SA, DM Name: {dm_name}", 200
    except NotFoundError:
        api_logger.exception("No NAs found, remind user to create NAs")
        sa = CB_SA[sa_id]
        return abort(400, f"No detected, please create Join point in Project {str(sa_id) + '-' + sa.sa_name}")
    except Exception as err:
        api_logger.exception(err)
        return abort(502, "Internal Server Error")


@apis.route('/subsystem/create_sa', methods=['POST'])
@requires_login
@orm.db_session
def create_sa():
    '''
    Creates an empty SA. Further steps must be triggered by refresh_sa after
        User has setup GUI connections(NAs).

    Args:
        cb_id: The ControlBoard this new SA belongs to.
        sa_name: Name of this SA given by the user.

    Returns:
        Status code: 200 / 400.
        proj_name: Project name for user to choose input sensors and output actuators.
    '''
    sa_spec = request.json
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
@requires_login
@orm.db_session
def delete_sa(sa_id=None):
    '''
    Delete SA with specified sa_id.

    Args:
        sa_id: ID of the requester SA.

    Returns:
        Status code: 200 / 400 / 500
        message: 'SA deleted successfully'.
    '''
    try:
        if None is sa_id:
            sa_id = int(request.get_data().decode("utf-8"))
        sa = CB_SA[sa_id]
        if sa.ag_token != "NotCreated":
            status = deregister_ag(sa, api_logger)
            if not status:
                api_logger.exception("Error delete SA, Deregister SA failed, check api log file")
                return "Delete SA failed, check api log files", 500
        status, message = delete_proj_ag(sa.p_id, api_logger)
        if not status:
            api_logger.exception("Error delete SA, Delete project failed, check api log file")
            api_logger.exception(f"Error msg from AG: {message}")
            return "Delete SA failed, check api log files", 500
        sa.delete()
        del running_sa[sa_id]
        api_logger.info(f"Delete Running SA, SA_ID: {sa.sa_id}")
        return "Delete SA succeed", 200
    except KeyError:
        api_logger.exception('Specified ControlBoard not running')
        return "Specified SA not found", 400


@apis.route('/subsystem/get_sa/<int:cb_id>', methods=['GET'])
@requires_login
@orm.db_session()
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
    if 0 == cb_id:
        return jsonify(list()), 200
    try:
        account = CB_Account.get(account=session["user"])
        if CB[cb_id] not in account.cb_set:
            raise NotAuthorizedError
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
    except NotAuthorizedError:
        api_logger.exception("Error getting SA, Requested CB is not shared with this user.")
        abort(403, "Not a superuser!")


@apis.route('/subsystem/get_accessible_proj/<string:user_name>', methods=['GET'])
@requires_login
@orm.db_session
def get_accessible_proj(user_name):
    '''
    Returns CB(Projects) granted to be controlled by user given `user_name`.

    Args:
        user_name: String, the user's account

    Returns:
        Status code: 200 / 500
        proj_list: A list of `cb_id`s that this user can reach.
    '''
    try:
        proj_list = list()
        req_account = CB_Account.get(account=user_name)
        for cb in req_account.cb_set:
            proj_list.append(cb.cb_id)
        return jsonify(proj_list), 200
    except Exception as err:
        api_logger.exception(err)
        abort(500)


@apis.route('/subsystem/set_pinned_field', methods=['POST'])
@requires_login
@orm.db_session
def set_pinned_field():
    '''
    Set SA(Fields) to pinned in CB given `cb_id` and `sa_id`.

    Args:
        cb_id: Int, the CB's primary key.
        to_pinned: List, SA_id of SAs to be pinned.

    Returns:
        Status code: 200 / 400 / 500
        Msg: Corresponding execution status.
    '''
    try:
        data = request.json
        cb_id, pinned_list = data["cb_id"], data["to_pinned"]
        sa_ids = set()
        # Check `sa_id`s contained in `pinned_list` are all belong to the CB given `cb_id`
        for sa in CB[cb_id].sa_set:
            sa_ids.add(sa.sa_id)
        for to_pinned in pinned_list:
            if to_pinned not in sa_ids:
                raise NotFoundError

        for sa_id in sa_ids:
            if sa_id in pinned_list:
                CB_SA[sa_id].pinned = True
            else:
                CB_SA[sa_id].pinned = False

        return "okay", 200
    except NotFoundError:
        api_logger.exception("Unrelated SA involved, abort request")
        abort(400)
    except Exception as err:
        api_logger.exception(err)
        abort(500)


@apis.route('/subsystem/cb_icon/<int:cb_id>', methods=["PUT"])
@requires_login
@orm.db_session
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
        account = CB_Account.get(account=session["user"])
        if not account.privilege:
            raise NotAuthorizedError
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
    except NotAuthorizedError:
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
@requires_login
@orm.db_session
def create_cb():
    '''
    Create a Empty ControlBoard that contains no SA(Field).

    Args:
        text: cb_name of this ControlBoard.

    Returns:
        Status Code: 200 / 400 / 401 / 500.
        Message: Corresponding execution result.
    '''
    new_cb = request.get_data().decode("utf-8")
    try:
        owner = CB_Account.get(account=session["user"])
        if None is owner:
            raise NotFoundError
        cb = CB(
            cb_name=new_cb,
            icon=env_config["env"]["default_icon"]
        )
        cb.account_set.add(owner)
        api_logger.info(f"Create ControlBoard by User {owner.account}, CB ID:  {cb.cb_id}")
    except NotFoundError:
        api_logger.exception("Error Create CB, No Such User!")
        abort(400, "Non-existed User!")
    except Exception as err:
        api_logger.exception(err)
        abort(502, "Unknown Error occurred, contact subsystem-admin to check error log!")
    return "Success", 200


@apis.route('/subsystem/delete_cb', methods=['POST'])
@requires_login
@orm.db_session
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
        account = CB_Account.get(account=session["user"])
        api_logger.info(f"Delete ControlBoard {cb_id} by User {account.account}")
        if not account.privilege:
            raise NotAuthorizedError
        if CB[cb_id].icon != env_config["env"]["default_icon"]:
            os.remove(os.path.join(os.path.normpath(env_config["env"]["icon_path"]), CB[cb_id].icon))
        for sa in CB[cb_id].sa_set:
            delete_sa(sa.sa_id)

        CB[cb_id].delete()  # By applying cascade deleting.
        return "Specified ControlBoard and subsequent Fields deleted."
    except NotAuthorizedError:
        api_logger.exception("Error Deleting ControlBoard, User is not a superuser.")
        abort(403, "Not a superuser!")
    except Exception as err:
        api_logger.exception("Unknown error occurred, error message as belows")
        api_logger.exception(err)
        abort(502, "Internal error occurred")


@apis.route('/subsystem/get_cb/<string:usr_account>', methods=['GET'])
@requires_login
@orm.db_session
def get_cb(usr_account):
    '''
    Returns all accessible CB list given user account

    Args: None

    Returns:
        Status code: 200 / 401 / 403
        accessible_cb: A Dict containing 2 lists
            accessibleProjects: A list containing all `CB_id`s owned/shared to this user.
            optionProjects: A list of CBs including all CBs shared to this user.

            If user is not a superuser, that `accessibleProjects` will be exactly the same as `optionProjects`.
            Otherwise `optionProjects` would contains all CBs.
    '''
    try:
        print(usr_account)
        if "self" == usr_account:  # Access current logined user's accessible CBs.
            usr_account = session["user"]
        current_user = CB_Account.get(account=session["user"])
        if 0 == current_user.privilege and usr_account != session["user"]:
            raise NotAuthorizedError
        account = CB_Account.get(account=usr_account)
        if None is account:
            raise NotFoundError
        accessible_cb = list()
        for cb in account.cb_set:
            accessible_cb.append(cb.cb_id)

        option_cb = list()
        if 2 == account.privilege:
            candidates = CB.select()
        else:
            candidates = account.cb_set
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
    except NotAuthorizedError:
        api_logger.exception("Error Getting ControlBoard, No such user.")
        # TODO: redirect to AAA login page.
        abort(401, "No such User")
    except NotFoundError:
        api_logger.exception("No such user")
        abort(403, "No such user")
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
        Status code: 200 / 403 / 500.
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
                "username": account.account
            })
        return jsonify(users), 200
    except NotFoundError:
        api_logger.exception("No such user")
        abort(403, "No such user")
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
    Adjust user privilege and accessible CB(Project)s

    Args:
        usr_name: String, account of the specified user.
        usr_profile: Dictionary containing two fields `privilege` and `accessible_cb`
            privilege: Int, ranging from 0~2, indicating user/superuser/admin individually.
            accessible_cb: List, cb_ids this user should be granted to access.

    Returns:
        Status code: 200 / 400 / 500
        Msg: Corresponding execution result.
    '''
    try:
        data = request.json
        print(data)
        account = CB_Account.get(account=usr_name)
        if None is account:
            raise NotFoundError
        account.privilege = data["privilege"]
        account.cb_set.clear()
        for cb_id in data["accessible_cb"]:
            account.cb_set.add(CB[cb_id])
        return "setup done", 200
    except NotFoundError:
        api_logger.exception("No Such Account")
        abort(400)
    except Exception as err:
        api_logger.exception(err)
        abort(500)
