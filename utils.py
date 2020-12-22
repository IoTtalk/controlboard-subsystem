import logging
import requests
import os
import uuid
import json
import asyncio


import zmq


from pony import orm
from tornado import ioloop
from zmq.eventloop.zmqstream import ZMQStream


from config import env_config, reg_config, use_v1
from models import UserRule, CB_Account, CB_SA, CB


# used to record AG SA. In format {sa_id: CB_SA entity}
running_sa = dict()

'''
used to record AG SA's rule status. In format
    {
        sa_id1: {
            sensor_alias1: {
                value: sensor value,
                prev_trigger: -10000 or an epoch time, -10000 means no need to use this field data.
                status: 'GREEN'/'RED'/'YELLOW'
            },
        },
    }
'''
running_status = dict()

# DF/DM id from IoTtalk to automatically create Project and DMO.
iottalk_info = dict()


log_root = env_config['env']['logroot']
if not os.path.isdir(log_root):
    os.makedirs(log_root)

default_rules = {
    'rule_type': 'sensor',
    'threshold_open': 0.,
    'threshold_close': 0,
    'comparison_open': 'notset',
    'comparison_close': 'notset',
    'mode': 'auto',
    'period': 0
}


def _post(url, data):
    '''
    AG post request worker

    Args:
        data: payload to be attached in the post request.

    Returns:
        res: response from AG.
    '''
    response = json.loads(
        requests.post(
            f'http://{env_config["env"]["host_ag"]}:{env_config["env"]["port_ag"]}/{url}/',
            json=data
        ).text
    )
    if url == "ccm_api":
        print(data, response)
    else:
        print(url, response)
    state = (response["state"] == "ok")
    return state, response


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

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)

    log_file_path = os.path.join(log_root, log_file + '.log')
    fh = logging.FileHandler(log_file_path)
    fh.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s - \t%(lineno)s - \t%(message)s')
    sh.setFormatter(formatter)
    fh.setFormatter(formatter)

    logger.addHandler(sh)
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
        cb_db: MySQL Database Connection
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
    cb_db.drop_all_tables(with_all_data=True)  # used to clean testcase
    while (retry_times < 3):
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
        with orm.db_session():
            test_account = CB_Account(
                account="test",
                privilege="1",
            )

            test_cb = CB(
                cb_name="test_cb",
                shared=0,
                account_set=test_account,
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

            test_rule = UserRule(
                actuator_alias="test_actuator",
                actuator_df="test_df",
                df_order=0,
                sensor_alias="test_sensor",
                period=0,
                sa=test_sa,
                mode='Sensor'
            )

            test_account.cb_set.add(test_cb)
            test_cb.sa_set.add(test_sa)
            test_sa.rule_set.add(test_rule)

        logger.info('\tTest database connection......done')
    except Exception as err:
        logger.exception(err)

    return


status_logger = make_logger("CB_status", "status")


def status_receiver(msgs):
    '''
    Receive execution status from AG SAs.

    Args:
        msgs: Messages sent from AG SAs.

    Returns: None
    '''
    for msg in msgs:
        status = json.loads(msg.decode("utf-8"))
        print("Server received", status)
        try:
            rule_id = status["rule_id"]
            running_status[rule_id] = status
            status_logger.info(f"Receive status from Rule {rule_id}")
            status_logger.info(status)
        except KeyError:
            status_logger.exception("Receive status error")


def connect_zmq(logger):
    '''
    Create ZMQ Listener for AG SA to sync rule status

    Args:
        logger: Logger object to write log in.

    Returns:
        socket: Created socket object for receiving messages from AG SA.
    '''
    asyncio.set_event_loop(asyncio.new_event_loop())
    context = zmq.Context.instance()
    socket = context.socket(zmq.SUB)
    socket.bind(f"tcp://*:{env_config['env']['port_zmq']}")
    socket.setsockopt(zmq.SUBSCRIBE, b"")

    stream = ZMQStream(socket)
    stream.on_recv(status_receiver)
    ioloop.IOLoop.instance().start()

    print('test end')


def get_iottalk_info(logger):
    '''
    Get Device ID/ Device Model ID from IoTtalk Server.

    Args:
        logger: System Logger to record this event.

    Returns:
        None
    '''
    try:
        data = {
            'api_name': 'devicemodel.get',
            'payload': {
                'dm': 'ControlBoard'
            }
        }
        state, response = _post('ccm_api', data)
        if not state:
            raise ValueError
        response = response["result"]
        iottalk_info['dm_id'] = response['dm_id']
        iottalk_info['df_id'] = list()
        for df in response["df_list"]:
            iottalk_info['df_id'].append(df['df_id'])
        logger.info('Fetch DF/DM id......done')
    except ValueError:
        logger.exception("Getting Device Model info failed.")
    except Exception as err:
        logger.exception(err)
    return


def create_proj_ag(sa, logger):
    '''
    Worker function to register to AG given sa entity and logger.

    Args:
        proj_name: SA entity object selected from PonyORM.
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating create procedure success or fail.
        p_id: Creatd integer Project ID retrived from AG.
    '''
    data = {
        "api_name": "project.create",
        "payload": {
            "p_name": sa.sa_name
        }
    }
    try:
        state, response = _post('ccm_api', data)
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
        status, response = _post('ccm_api', data)
        return status, response
    except Exception as err:
        logger.exception(err)
        return False


def create_do_ag(p_id, logger):
    '''
    Creates Assigned Device Object Given dm_id, df_id and p_id.

    Args:
        p_id: IoTtalk Project ID to create DeviceObject(DO).
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating create DO success or fail.
        do_id: Created integer DO ID retrived from AG.
    '''
    data = {
        "api_name": "deviceobject.create",
        "payload": {
            "p_id": p_id,
            "dm_name": "ControlBoard",
            "dfs": iottalk_info["df_id"]
        }
    }
    try:
        status, response = _post('ccm_api', data)
        logger.info('\tCreate DO\t......done')
        return status, response["result"]
    except Exception as err:
        logger.exception(err)
        return False, -1


def register_ag(sa, logger):
    '''
    Worker function to register to AG given sa entity and logger.

    Args:
        sa: The CB_SA Entity to be registered.
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating register status.
        ag_token: Token retrived from AG.
    '''
    try:
        new_sa = open('./CB_SA.py', 'r').read().format(
            sa_id=sa.sa_id, config=reg_config, mac_addr=sa.mac_addr, sa_name=sa.sa_name)
        data = {
            "version": int(env_config["IoTtalk"]["version"]),
            "code": new_sa
        }

        state, response = _post('create_device', data)
        return state, response["token"]
    except KeyError:
        logger.exception('CB_SA.py Key Error, check parameter passed in or brackets in the code')
        return False, "Error"
    except Exception as err:
        logger.exception(err)
        return False, "Error"


def deregister_ag(sa, logger):
    '''
    Worker function to deregister AG device.

    Args:
        sa: SA entity object selected from PonyORM.
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating register status.
    '''

    try:
        data = {
            'token': sa.ag_token
        }
        _post('delete_device', data)

        with orm.db_session():
            CB_SA[sa.sa_id].delete()
        return True
    except Exception as err:
        logger.exception(err)
        return False


def bind_device_ag(mac_addr, p_id, do_id, logger):
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
            status, response = _post('ccm_api', data)
            if not status:
                raise ValueError
            response = response["result"]
            logger.info('\tGet Device\t......done')
            device = None
            for candidate in response:
                if candidate["mac_addr"] == mac_addr:
                    device = candidate
                    break
            if device is None:
                raise ValueError
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
                status, response = _post("ccm_api", data)
            logger.info("\tBind device\t......done")
            return status, response["result"]
    except ValueError:
        logger.exception("Device to bind not found, either SA code error causing registration failed or Server latency")
        return False, "DM not found"
    except Exception as err:
        logger.exception(err)
        return False, "DM not found"


def get_na_ag(p_id, na_id, logger):
    '''
    Get a specific NetworkApplication given p_id and na_id.

    Args:
        p_id: Integer indicating which SA to query.
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
        state, res = _post("ccm_api", data)
        return state, res["result"]
    except Exception as err:
        logger.exception(err)
        return False, "Send request to query NA failed, check API log."
