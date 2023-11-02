import logging
import requests
import re
import os
import uuid
import json
import asyncio
import time

import zmq


from pony import orm
from tornado import ioloop
from zmq.eventloop.zmqstream import ZMQStream


from config import env_config, reg_config, use_v1
from exceptions import CCMAPIFailError #pass
from models import CBElement, CB_Account, CB, CB_Sensor


# used to record AG SA. In format {sa_id: CB_SA entity}
running_cb = dict()

'''#TODO
used to record AG SA's rule status. In format
    {
        rule_id: {
            value: sensor value,
            prev_trigger: -10000 or an epoch time, -10000 means no need to use this field data.
            status: 'GREEN'/'RED'/'YELLOW'
        },
    }
'''
running_status = dict()

# DF/DM id from IoTtalk to automatically create Project and DMO.
iottalk_info = dict()


log_root = env_config['env']['logroot']
if not os.path.isdir(log_root):
    os.makedirs(log_root)


def _post(url, data, logger):
    '''
    AG post request worker

    Args:
        data: payload to be attached in the post request.

    Returns:
        res: response from AG.
    '''
    try:
        response = json.loads(
            requests.post(
                f'http://{env_config["env"]["host_ag"]}:{env_config["env"]["port_ag"]}/{url}/',
                json=data
            ).text
        )
        state = (response["state"] == "ok")
        return state, response
    except Exception as err:
        logger.exception(err)
        return False, "failed at sending request to AG"


def make_logger(log_name, log_file):
    '''
    Inits a Logger with title log_name and file name that stores informations from this logger

    Args:
        log_name: Title of this logger, used in presentation of log streaming.
        log_file: File name to store logs from this logger.

    Returns:
        A logger object with fixed logging format.
    '''
    logger = logging.getLogger(f'[{log_name}]')
    logger.setLevel(logging.INFO)

    log_file_path = os.path.join(log_root, log_file + '.log')
    fh = logging.FileHandler(log_file_path)
    fh.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s - \t%(lineno)s - \t%(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger


def connect_db(logger, cb_db):
    '''
    Create a connection to MySQL Database specified in config

    Args:
        config: Config object read from user specified .ini file.
        logger: Logger object to write log in.
        cb_db: Database object to be bind.

    Returns:
        cb_db: PonyORM Database Connection
    '''
    retry_times = 0
    if env_config['db']['database'] == 'sqlite':
        cb_db.bind(
            provider='sqlite',
            filename='cb_db.sqlite',
            create_db=True
        )
    else:
        cb_db.bind(
            provider='mysql',
            host=env_config['db']['host'],
            user=env_config['db']['user'],
            passwd=env_config['db']['pwd'],
            db=env_config['db']['dbname'],
            port=int(env_config['db']['port'])
        )
    cb_db.generate_mapping(check_tables=False)
    if env_config["db"]["reset"] == "1":
        logger.info("Reset Database")
        cb_db.drop_all_tables(with_all_data=True)  # used to clean testcase
    while (retry_times < 9):
        try:
            cb_db.create_tables()
            logger.info('\tConnecting to Database\t......done')
            break
        except orm.dbapiprovider.InternalError:
            logger.exception('\t\tInternal Error Encountered, trying to remove tables and reconnect...')
            cb_db.drop_all_tables(with_all_data=True)
            cb_db.disconnect()
            retry_times += 1
    return


@orm.db_session
def test_db(logger):
    '''
    Write dummy data to database for testing connection.

    Args:
        logger: Logger object to write log in.

    Returns: None
    '''
    try:
        test_account = CB_Account(
            account="pcs54784@gmail.com",
            privilege="1",
        )

        dummy_account = CB_Account(
            account="example@gmail.com",
            privilege="0",
        )

        # admin = CB_Account(
        #     account="yb",
        #     privilege="2",
        # )

        test_cb = CB(
            cb_name="test_cb1",
            icon="0_landscape.svg"
        )

        dummy_cb = CB(
            cb_name="test_cb",
            icon="0_landscape.svg"
        )

        test_sa = CB_SA(
            sa_name="test_sa",
            ag_token="testagtoken",
            mac_addr=str(uuid.uuid4()),
            p_id=-1,
            do_id="1234567",
            cb=test_cb,
            pinned=True
        )

        test_rule = CBElement(
            actuator_alias="test_actuator",
            actuator_df="test_df",
            df_order=0,
            duty_pos=0,
            sa=test_sa,
            mode='Sensor'
        )

        test_account.cb_set.add(test_cb)
        dummy_account.cb_set.add(dummy_cb)
        test_cb.sa_set.add(test_sa)
        test_sa.rule_set.add(test_rule)

        logger.info('\tTest database connection......done')
    except Exception as err:
        logger.exception(err)

    return


status_logger = make_logger("CB_status", "status")


@orm.db_session
def status_receiver(msgs):
    '''
    Receive execution status from AG SAs.

    e.g. msg in msgs = {
            "prev_trigger": -10000, 
            "status": "GREEN", 
            "value": {
                "538": -27.391017263337368, 
                "544": 21.475446558578696
            }, 
            "rule_id": 3, 
            "prev_status": "OFF"
        }

    Args:
        msgs: Messages sent from AG SAs.

    Returns: None
    '''
    for msg in msgs:
        try:
            status = json.loads(msg.decode("utf-8"))
            rule_id = status["rule_id"]
            if None is CBElement.get(rule_id=rule_id):  # To filter out messages of deleted CBElements stuck at the queue
                continue
            if rule_id in running_status:
                if running_status[rule_id]["status"] != status["status"]:
                    msg = (
                        f"CBElement NO.{rule_id}'s status changed to {status['status']}\n"
                        f"Value: {status['value']}, Previous Triggered Epoch Time: {status['prev_trigger']}"
                    )
                    status_logger.info(msg)
            else:
                msg = {
                    f"CBElement NO.{rule_id}'s first status log: {status['status']}\n"
                    f"Value: {status['value']}, Previous Triggered Epoch Time: {status['prev_trigger']}"
                }
                status_logger.info(msg)
            running_status[rule_id] = status
        except Exception as err:
            status_logger.exception(err)


def connect_zmq(logger):
    '''
    Create ZMQ Listener for AG SA to sync rule status

    Args:
        logger: Logger object to write log in.

    Returns:
        socket: Created socket object for receiving messages from AG SA.
    '''
    logger.info("\tCreate ZMQ Listener...")
    asyncio.set_event_loop(asyncio.new_event_loop())
    context = zmq.Context.instance()
    socket = context.socket(zmq.SUB)
    socket.bind(f"tcp://*:{env_config['env']['port_zmq']}")
    socket.setsockopt(zmq.SUBSCRIBE, b"")

    stream = ZMQStream(socket)
    stream.on_recv(status_receiver)
    ioloop.IOLoop.instance().start()

    logger.info("\tZMQ Listener binded")
    return


def get_iottalk_info(logger):
    '''
    Get Device ID/ Device Model ID from IoTtalk Server.

    Args:
        logger: System Logger to record this event.

    Returns:
        None
    '''
    try:
        # Get the ID of ControlBoard's device model for automatic initialization.
        data = {
            'api_name': 'devicemodel.get',
            'payload': {
                'dm': 'ControlBoard'
            }
        }
        state, response = _post('ccm_api', data, logger)
        if not state:
            logger.error("Get DM failed")
            raise CCMAPIFailError
        response = response["result"]
        iottalk_info['dm_id'] = response['dm_id']
        iottalk_info['df_id'] = list()
        for df in response["df_list"]:
            order = int(re.search(r"\d+", df["df_name"]).group(0))
            if order < 10:
                iottalk_info['df_id'].append(df['df_id'])
        logger.info('Fetch DF/DM id......done')

        # Get the IDs for the cb_join and cb_transform function for automatic function setup after the admin finishes NA configuration.
        data = {
            "api_name": "function.list",
            "payload": {}
        }
        state, res = _post("ccm_api", data, logger)
        if not state:
            logger.error("Get function failed")
            raise CCMAPIFailError
        for fn in res["result"]:
            if fn["fn_name"] == "cb_join":
                iottalk_info["fn_join"] = fn["fn_id"]
            elif fn["fn_name"] == "cb_transform":
                iottalk_info["fn_transform"] = fn["fn_id"]
            elif fn["fn_name"] == "cb_sensor_idf":
                iottalk_info["fn_sensor_idf"] = fn["fn_id"]
            elif fn["fn_name"] == "cb_multi_join":
                iottalk_info["fn_multi_join"] = fn["fn_id"]

        if "fn_join" not in iottalk_info:
            iottalk_info["fn_join"] = create_fn_ag("./v1_func/CB_join.py", "cb_join", logger)
        if "fn_transform" not in iottalk_info:
            iottalk_info["fn_transform"] = create_fn_ag("./v1_func/CB_transform.py", "cb_transform", logger)
        if "fn_sensor_idf" not in iottalk_info:
            iottalk_info["fn_sensor_idf"] = create_fn_ag("./v1_func/CB_sensorIDF.py", "cb_sensor_idf", logger)
        if "fn_multi_join" not in iottalk_info:
            iottalk_info["fn_multi_join"] = create_fn_ag("./v1_func/CB_multijoin.py", "cb_multi_join", logger)
        logger.info(iottalk_info)
    except CCMAPIFailError:
        logger.exception("Getting IoTtalk info failed. check log")
    except Exception as err:
        logger.exception(err)
    return


def get_df_ag(df_name, logger):
    '''
    Worker function to get ID of a specific Device Feature.

    Args:
        df_name: String, name of the Device Feature.
        logger: Logger object to write log in.

    Returns:
        df_id: Integer, result from AG.

    '''
    data = {
        "api_name": "devicefeature.get",
        "payload": {
            "df": df_name
        }
    }
    try:
        state, response = _post('ccm_api', data, logger)
        if not state:
            raise CCMAPIFailError
        logger.info('\tGetting DF id\t......done')
        return response["result"]
    except Exception as err:
        logger.exception(err)
        return -1


def get_proj_ag(cb_name, logger):
    '''
    Worker function to get IoTtalk Project infomation given CB name and logger.

    Args:
        cb_name: CB's name to be created.
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating create procedure success or fail.
        project_info: Info of the requested project
    '''
    data = {
        "api_name": "project.get",
        "payload": {
            "p_id": cb_name
        }
    }
    try:
        state, response = _post('ccm_api', data, logger)
        if not state:
            raise CCMAPIFailError
        logger.info('Get Project\t......done')
        return state, response["result"]
    except Exception as err:
        logger.exception(err)
        return False, -1


def create_proj_ag(cb_name, logger):
    '''
    Worker function to create IoTtalk Project given CB name and logger.

    Args:
        cb_name: CB's name to be created.
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating create procedure success or fail.
        p_id: Creatd integer Project ID retrived from AG.
    '''
    data = {
        "api_name": "project.create",
        "payload": {
            "p_name": cb_name
        }
    }
    try:
        state, response = _post('ccm_api', data, logger)
        print("create_proj_ag response : ", response)
        if not state:
            raise CCMAPIFailError
        logger.info('\tCreate Project\t......done')
        return state, int(response["result"])
    except Exception as err:
        logger.exception(err)
        return False, -1


def delete_proj_ag(p_id, logger):
    '''
    Delete IoTtalk Project given p_id

    Args:
        p_id: ID of target IoTtalk Project.
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating deleting project success or fail.
    '''
    data = {
        "api_name": "project.delete",
        "payload": {
            "p_id": p_id,
        }
    }
    try:
        status, response = _post('ccm_api', data, logger)
        if not status:
            raise CCMAPIFailError
        return status, response
    except Exception as err:
        logger.exception(err)
        return False


def create_do_ag(p_id, df_id, dm_name, logger):
    '''
    Creates Assigned Device Object Given dm_name, df_id and p_id.

    Args:
        p_id: Integer, IoTtalk Project ID to create DeviceObject(DO).
        df_id: List, DF ids of a specific device model.
        dm_name: str, name of a specific device model.
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating create DO success or fail.
        do_id: Created integer DO ID retrived from AG.
    '''
    data = {
        "api_name": "deviceobject.create",
        "payload": {
            "p_id": p_id,
            "dm_name": dm_name,
            "dfs": df_id
        }
    }
    try:
        status, response = _post('ccm_api', data, logger)
        if not status:
            raise CCMAPIFailError
        logger.info('\tCreate DO\t......done')
        print("hello                ", response["result"])
        return status, response["result"]
    except CCMAPIFailError:
        logger.exception("CCM API request failed")
        return False, -1
    except Exception as err:
        logger.exception(err)
        return False, -1


def delete_do_ag(p_id, do_id, logger):
    '''
    Deletes Assigned Device Object Given p_id and do_id.

    Args:
        p_id: Integer, IoTtalk Project ID to delete DeviceObject(DO).
        do_id: Integer, id of DO to be deleted.
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating create DO success or fail.
    '''
    data = {
        "api_name": "deviceobject.delete",
        "payload": {
            "p_id": p_id,
            "do_id": do_id
        }
    }
    try:
        status, response = _post('ccm_api', data, logger)
        if not status:
            raise CCMAPIFailError
        logger.info(f'\tDelete DO {response["result"]}\t......done')
        return status, response["result"]
    except CCMAPIFailError:
        logger.exception("CCM API request failed")
        return False, -1
    except Exception as err:
        logger.exception(err)
        return False, -1


def register_ag(cb, logger):
    logger.info('\tTimestamp\t--> Function register_ag')

    '''
    Worker function to register to AG given cb entity and logger.

    Args:
        cb: The CB Entity to be registered.
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating register status.
        ag_token: Token retrived from AG.
    '''
    try:
        rules = dict()
        for rule in cb.rule_set:
            sen_data = list()
            for sen_rule in rule.sensor_set:
                sen_data.append(sen_rule.to_dict())
            #print(sen_data)
            sorted_sen_data = sorted(sen_data, key=lambda d: d['sensor_index']) # sort CB_Sensor by sensor_index
            cb_sa_data = rule.to_dict()
            cb_sa_data["sensors_data"] = sorted_sen_data # add CB_Sensor data into CBElement data in dict type
            rules[rule.df_order] = cb_sa_data
        print("\nreg_config : ", reg_config)
        print("\nrules : ", rules)
        print("\ncb.cb_id : ", cb.cb_id)
        print("\ncb.mac_addr : ", cb.mac_addr)
        print("\ncb.cb_name : ", cb.cb_name)
        new_sa = open('./CB_SA.py', 'r').read().format(
            sa_id=cb.cb_id, config=reg_config, mac_addr=cb.mac_addr, sa_name=cb.cb_name, rules=rules)
        # new_sa = open('./DAI.py', 'r').read()
        time.sleep(0.02)
        data = {
            "version": int(env_config["IoTtalk"]["version"]),
            "code": new_sa
        }

        state, response = _post('create_device', data, logger)
        if not state:
            raise CCMAPIFailError
        return state, response["token"]
    except KeyError:
        logger.exception('CB_SA.py Key Error, check parameter passed in or brackets in the code, format will replace the string in brackets')
        return False, "Error"
    except Exception as err:
        logger.exception(err)
        return False, "Error"


def deregister_ag(token, logger):
    logger.info('\tTimestamp\t--> Function deregister_ag')

    '''
    Worker function to deregister AG device.

    Args:
        token: AG Device token to be deleted.
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating register status.
    '''

    try:
        data = {
            'token': token
        }
        status, res = _post('delete_device', data, logger)
        if not status:
            logger.exception(res)
            raise CCMAPIFailError
        return True
    except Exception as err:
        logger.exception(err)
        return False


def bind_device_ag(mac_addr, p_id, do_id, logger):
    logger.info('\tTimestamp\t--> Function bind_device_ag')
    '''
    Bind corresponding device to assigned DO given do_id and p_id.

    Args:
        mac_addr: MAC Address of the registered CB_SA,
        p_id: ID of the assigned IoTtalk Project.
        do_id: A list containing 2 IDs of the DO in IoTtalk Project (v1).
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating binding status.
        msg: Corresponding DM's name or failure message.
    '''
    try:
        if use_v1:
            data = {
                "api_name": "device.get",
                "payload": {
                    "p_id": p_id,
                    "do_id": do_id[0]
                }
            }
            # print("sleep 1 seconds...")
            # time.sleep(0.2)
            # print("sleep done")
            status, response = _post('ccm_api', data, logger)
            if not status:
                raise CCMAPIFailError
            response = response["result"]
            logger.info('\tGet Device\t......done')
            device = None
            for candidate in response:
                if candidate["mac_addr"] == mac_addr:
                    device = candidate
                    break
            if device is None:
                raise CCMAPIFailError
            for id in do_id:
                print(id)
                data = {
                    "api_name": "device.bind",
                    "payload": {
                        "p_id": p_id,
                        "do_id": id,
                        "d_id": device["d_id"]
                    }
                }
                status, response = _post("ccm_api", data, logger)
                if not status:
                    raise CCMAPIFailError
            logger.info("\tBind device\t......done")
            return status, response["result"]
    except CCMAPIFailError:
        logger.exception("Device to bind not found, either SA code error causing registration failed or Server latency")
        return False, "DM not found"
    except Exception as err:
        logger.exception(err)
        return False, "DM not found"


def create_na_ag(p_id, na_name, na_idx, dfo_ids, logger):
    '''
    Create a join node with given dfo_ids

    Args:
        p_id: The Project ID
        na_name: The name of the desired join node.
        na_idx: The index of the na.
        dfo_ids: The device feature objects to be connected.

    Returns:

    '''
    data = {
        "api_name": "networkapplication.create",
        "payload": {
            "p_id": p_id,
            "joins": dfo_ids
        }
    }
    try:
        state, res = _post("ccm_api", data, logger)
        if not state:
            raise CCMAPIFailError
        return state, res["result"]
    except CCMAPIFailError:
        logger.exception("Create NA failed")
        return False, "AG returned bad response"
    except Exception as err:
        logger.exception(err)
        return False, "Send request to create NA failed, check API log."


def get_na_ag(p_id, na_id, logger):
    '''
    Get a specific NetworkApplication given p_id and na_id.

    Args:
        p_id: The Project ID.
        na_id: Integer indicating which NA to query.

    Returns:
        status: Boolean indicating ccm_api execution result.
        msg: NA's info or CCM API failure message.
    '''
    data = {
        "api_name": "networkapplication.get",
        "payload": {
            "p_id": p_id,
            "na_id": na_id
        }
    }
    try:
        state, res = _post("ccm_api", data, logger)
        '''
        the returned json will have the following format
        refer to api/v0/project/`p_id`/na/`na_id` for example
        {
            "result":
            {
                "fn_list": [],
                "multiple": [],
                "na_id": integer,
                "na_idx": integer,
                "na_name": string,
                "p_id": integer
                "input":
                [
                    {
                        "alias_name",
                        "df_id",
                        "df_name",
                        "df_type",
                        "dfmp": [   // stands for Device Feature Modular parameters
                            {
                                "color",
                                "dfo_id",
                                "fn_id",
                                "idf_type",
                                "max",
                                "min",
                                "na_id",
                                "normalization",
                                "param_i"
                            }
                        ],
                        "dfo_id",
                        "dm_name",
                        "fn_list":
                        [
                            {
                                "fn_id",
                                "fn_name"
                            }
                        ],
                        "mac_addr"
                    }
                ],
                output: same as input
            }
        }
        '''
        if not state:
            raise CCMAPIFailError
        return state, res["result"]
    except CCMAPIFailError:
        logger.exception("Get NA failed")
        return False, "AG returned bad response"
    except Exception as err:
        logger.exception(err)
        return False, "Send request to query NA failed, check API log."


def delete_na_ag(na_id, p_id, logger):
    '''
    Delete a specific NetworkApplication given p_id and na_id.

    Args:
        p_id: Integer indicating which CB to delete NA.
        na_id: Integer indicating which NA to delete.

    Returns:
        status: Boolean indicating ccm_api execution result.
        msg: NA's info or CCM API failure message.
    '''
    data = {
        "api_name": "networkapplication.delete",
        "payload": {
            "p_id": p_id,
            "na_id": na_id
        }
    }
    try:
        state, res = _post("ccm_api", data, logger)
        if not state:
            raise CCMAPIFailError
        return state, res["result"]
    except CCMAPIFailError:
        logger.exception("Delete NA failed")
        return False, "AG returned bad response"
    except Exception as err:
        logger.exception(err)
        return False, "Send request to query NA failed, check API log."


def create_fn_ag(file_name, fn_name, logger):
    '''
    Create a IoTtalk function with its content identical to the code in `file_name`

    Args:
        file_name: The file path to be uploaded as a function to the IoTtalk server.
        fn_name: The name of the function.

    Returns:
        fn_id: The id of the newly created function.
    '''
    data = {
        "api_name": "function.create",
        "payload": {
            "fn_name": fn_name,
            "code": open(file_name, 'r').read()
        }
    }
    try:
        state, res = _post("ccm_api", data, logger)
        if not state:
            raise CCMAPIFailError
        return res["result"]
    except CCMAPIFailError:
        logger.error("Create fn failed")
        return -1
    except Exception as err:
        logger.exception(err)
        return -1

def set_multi_sensor_fn_ag(p_id, na_info, logger):
    '''
    Set specified na's multi_join function and sensor_idf funtion
    iottalk_info["fn_sensor_idf"] store cb_sensor_idf funtion index
    iottalk_info["fn_multi_join"] store cb_multi_join funtion index

    Args:
        na_info: result from `get_na_ag`
    '''
    dfm_list = list()

    for index in na_info["input"]:
        if index["dm_name"] != "ControlBoard":  # The IDF is an input device.
            index["dfmp"][0]["fn_id"] = iottalk_info["fn_sensor_idf"]
        dfm_list.append({"dfo_id": index["dfo_id"], "dfmp_list": index["dfmp"]})

    data = {
        "api_name": "networkapplication.update",
        "payload": {
            "p_id": p_id,
            "na_id": na_info["na_id"],
            "dfm_list": dfm_list,
            "na_name": na_info["na_name"],
            "multiplejoin_fn_id": iottalk_info["fn_multi_join"] # Set the multiple join function
        }
    }
    try:
        state, res = _post("ccm_api", data, logger)
        print("change multi-sensor fn result:", res)
        if not state:
            raise CCMAPIFailError
        return state, res["result"]
    except CCMAPIFailError:
        logger.exception("Change multi-sensor FN failed")
        return False, "AG returned bad response"
    except Exception as err:
        logger.exception(err)
        return False, "Send request to query NA failed, check API log."

def set_fn_ag(p_id, na_info, logger):
    '''
    Set specified na's join function to CB's function
    iottalk_info["fn_join"] store cb_join funtion index
    iottalk_info["fn_transform"] store cb_transform funtion index

    Args:
        na_info: result from `get_na_ag`
    '''
    dfm_list = list()
    for index in na_info["input"]:
        dfm_list.append({"dfo_id": index["dfo_id"], "dfmp_list": index["dfmp"]})

    for index in na_info['output']:
        if index["dm_name"] != "ControlBoard":  # The ODF is an output device.
            index["dfmp"][0]["fn_id"] = iottalk_info["fn_transform"]
        dfm_list.append({"dfo_id": index["dfo_id"], "dfmp_list": index["dfmp"]})

    dfm_list[0]['dfmp_list'][0]['fn_id'] = iottalk_info["fn_join"]  # Set the IDF function of IDF CBElement-I to ControlBoard

    data = {
        "api_name": "networkapplication.update",
        "payload": {
            "p_id": p_id,
            "na_id": na_info["na_id"],
            "dfm_list": dfm_list,
            "na_name": na_info["na_name"]
        }
    }
    try:
        state, res = _post("ccm_api", data, logger)
        print("change fn result:", res)
        if not state:
            raise CCMAPIFailError
        return state, res["result"]
    except CCMAPIFailError:
        logger.exception("Change FN failed")
        return False, "AG returned bad response"
    except Exception as err:
        logger.exception(err)
        return False, "Send request to query NA failed, check API log."
