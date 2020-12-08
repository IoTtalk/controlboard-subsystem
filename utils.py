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
    return requests.post(f'http://{env_config["env"]["host_ag"]}:{env_config["env"]["port_ag"]}/autogen/{url}', data=data)


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

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
            logger.error('\t\tInternal Error Encountered, try remove tables and reconnect...')
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
                account='test',
                privilige='1',
            )

            test_sa = CB_SA(
                cb_name='test_sa',
                ag_token="testagtoken",
                mac_addr=str(uuid.uuid4()),
                p_id=-1,
                do_id="1234567"
            )

            test_cb = CB(
                field_name="test_cb",
                shared=0,
                account_set=test_account
            )

            test_rule = UserRule(
                rule_type='Sensor',
                actuator_alias='test_actuator',
                sensor_alias="test_sensor",
                period=0,
                sa=test_sa,
                mode='auto'
            )

            test_account.cb_set.add(test_cb)
            test_cb.sa_set.add(test_sa)
            test_sa.rule_set.add(test_rule)

        logger.info('\tTest database connection......done')
    except Exception as err:
        logger.error(err)

    return


status_logger = make_logger('cb_status', 'status')


def status_receiver(msg):
    '''
    Receive execution status from AG SAs.

    Args:
        msg: Message sent from AG SAs.

    Returns: None
    '''
    status = json.loads(msg[0].decode('utf-8'))
    print("Server received", status)
    try:
        cb_id = status["cb_id"]
        status.pop("cb_id")
        running_status[cb_id] = status
        status_logger.info(f"Receive status from CB {cb_id}")
        status_logger.info(status)
    except KeyError:
        status_logger.error("Receive status error")


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
            'payload': json.dumps({
                'dm': 'ControlBoard'
            })
        }
        response = _post('ccm_api', data).text
        response = json.loads(response)
        iottalk_info['dm_id'] = response['dm_id']
        iottalk_info['df_id'] = list()
        for df in response["df_list"]:
            iottalk_info['df_id'].append(df['df_id'])
        logger.info('Fetch DF/DM id......done')

    except Exception as err:
        logger.error(err)

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
        "payload": json.dumps({
            "p_name": sa.cb_name
        })
    }
    try:
        response = _post('ccm_api', data)
        logger.info('\tCreate Project\t......done')

        return True, int(response.text)
    except Exception as err:
        logger.error(err)
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
        "payload": json.dumps({
            "p_id": p_id,
        })
    }
    try:
        _post('ccm_api', data)
        return True
    except Exception as err:
        logger.error(err)
        return False


def create_do_ag(p_id, logger):
    '''
    Creates Assigned Device Object Given dm_id, df_id and p_id.

    Args:
        p_id: IoTtalk Project ID to create DeviceObject(DO).
        logger: Logger object to write log in.

    Returns:
        status: Boolean value indicating create DO success or fail.
        do_id: Creatd integer DO ID retrived from AG.
    '''
    data = {
        "api_name": "deviceobject.create",
        "payload": json.dumps({
            "p_id": p_id,
            "dm_name": "ControlBoard",
            "dfs": iottalk_info["df_id"]
        })
    }
    try:
        response = _post('ccm_api', data)
        logger.info('\tCreate DO\t......done')
        return True, json.loads(response.text)
    except Exception as err:
        logger.error(err)
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
        new_sa = open('./CB_SA.py', 'r').read().format(cb_id=sa.cb_id, config=reg_config, mac_addr=sa.mac_addr)
        data = {
            'version': env_config["IoTtalk"]["version"],
            'code': new_sa
        }

        response = _post('create_device', data).text
        return True, response

    except KeyError:
        logger.error('CB_SA.py Key Error, check parameter passed in or brackets in the code')
        return False, "Error"

    except Exception as err:
        logger.error(err)
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
            CB_SA[sa.cb_id].delete()
        return True
    except Exception as err:
        logger.error(err)
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
    '''
    try:
        if use_v1:
            data = {
                "api_name": "device.get",
                "payload": json.dumps({
                    "p_id": p_id,
                    "do_id": do_id[0]
                })
            }
            response = _post('ccm_api', data)
            response = json.loads(response.text)
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
                    "payload": json.dumps({
                        "p_id": p_id,
                        "do_id": id,
                        "d_id": device['d_id']
                    })
                }
                _post('ccm_api', data)
            logger.info('\tBind device\t......done')
            return True
    except ValueError:
        logger.error("Device to bind not found")
        return False
    except Exception as err:
        logger.error(err)
        return False
