import time
import logging


from collections import deque


import DAN
import shared_vars


from config import env_config


logger = logging.getLogger('[PullingThread]')
logger.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

fh = logging.FileHandler('Pulling.log')
fh.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)

logger.addHandler(ch)
logger.addHandler(fh)


def record_his_data(data, sensor_alias):
    """
    Sensor data collector, keeps the latest <df_his_record_len> records of history data in memory.

    Args:
        data: data pulled from IoTTalk server. Form of data depends on the sensor.
        sensor_alias: alias of sensor stored in memory. Type String.

    Returns
        None
    """
    if sensor_alias not in shared_vars.df_hist_val:
        shared_vars.df_hist_val[sensor_alias] = deque(maxlen=env_config.df_his_record_len)
        shared_vars.df_hist_len[sensor_alias] = 0

    if shared_vars.df_hist_len[sensor_alias] >= shared_vars.df_hist_val[sensor_alias].maxlen:
        shared_vars.df_hist_val[sensor_alias].popleft()
        shared_vars.df_hist_len[sensor_alias] -= 1

    shared_vars.df_hist_val[sensor_alias].append(data)
    shared_vars.df_hist_len[sensor_alias] += 1

    return


def on_data():
    """
    The interface of data pulling procedure. Pull datum every 5 secs.

    Args:
        None

    Returns:
        None
    """
    logger.info('Creating Pulling Data Thread')
    sensor_list = list()

    for actuator_alias in shared_vars.mappings:
        sensor_alias = shared_vars.mappings[actuator_alias][0]
        order = shared_vars.mappings[actuator_alias][1]
        sensor_name = 'Threshold' + '-O' + str(order + 1)
        sensor_list.append((sensor_alias, sensor_name))

    while shared_vars.pulling_flag:
        try:
            for sensor_alias, sensor_name in sensor_list:
                data = DAN.pull(sensor_name)
                if data is not None:
                    record_his_data(data[0], sensor_alias)
                    logger.info(f"Pull data {data[0]} from {sensor_alias}")

        except Exception as ep:
            logger.warn(ep)
        time.sleep(5)

    print('Pulling Thread stops')

    return
