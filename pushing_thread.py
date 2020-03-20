import time
import logging


from datetime import datetime, date, timedelta


import DAN
import shared_vars


logger = logging.getLogger('[PushingThread]')
logger.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

fh = logging.FileHandler('Pushing.log')
fh.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)

logger.addHandler(ch)
logger.addHandler(fh)


def bigger(data, threshold, avg):
    if data > threshold:
        triggered = True
        color = 'green'
    else:
        triggered = False
        print('bigger', 0.5 * (threshold - avg) + avg)
        if data > 0.5 * (threshold - avg) + avg:
            color = 'yellow'
        else:
            color = 'unchanged'

    return triggered, color


def smaller(data, threshold, avg):
    if data < threshold:
        triggered = True
        color = 'green'
    else:
        triggered = False
        print('smaller', 0.22 * (avg - threshold) + threshold)
        if data < 0.22 * (avg - threshold) + threshold:
            print(data, 'yellow')
            color = 'yellow'
        else:
            color = 'unchanged'
    return triggered, color


def bigger_equal(data, threshold, avg):
    if data >= threshold:
        triggered = True
        color = 'green'
    else:
        print('biggerequal', 0.78 * (threshold - avg) + avg)
        triggered = False
        if data > 0.78 * (threshold - avg) + avg:
            color = 'yellow'
        else:
            color = 'unchanged'

    return triggered, color


def smaller_equal(data, threshold, avg):
    if data <= threshold:
        triggered = True
        color = 'green'
    else:
        triggered = False
        print('smallerequal', 0.22 * (avg - threshold) + threshold)
        if data < 0.22 * (avg - threshold) + threshold:
            color = 'yellow'
        else:
            color = 'unchanged'
    return triggered, color


conditionHandler = {
    'bigger': bigger,
    'smaller': smaller,
    'biggerandequal': bigger_equal,
    'smallerandequal': smaller_equal
}


def sensor_checker(comparison, threshold, data, action, actuator, actuator_alias, sensor_alias):
    avg = sum(list(shared_vars.df_hist_val[sensor_alias])) / len(shared_vars.df_hist_val[sensor_alias])
    print('current avg:', avg)
    triggered, color = conditionHandler[comparison](float(data), float(threshold), avg)
    to_trigger = 'STAY'
    print('Satisfied?', triggered)
    if triggered:
        if action == 'open':
            to_trigger = 'OPEN'
            # logger.info(f'sensor {sensor_alias} triggered {actuator_alias}')
            shared_vars.rule_info[actuator_alias]['status'] = 'green'
        else:
            # logger.info(f'sensor {sensor_alias} closed {actuator_alias}')
            to_trigger = 'CLOSE'
            shared_vars.rule_info[actuator_alias]['status'] = 'red'
    if color == 'yellow':
        shared_vars.rule_info[actuator_alias]['status'] = color

    return to_trigger


def time_checker(actuator_alias, sensor_alias, order):
    current = datetime.now()
    actuator_name = 'Trigger' + '-I' + str(order + 1)
    time_open = datetime.combine(date.today(), shared_vars.rule_info[actuator_alias]['time_open'])
    time_close = datetime.combine(date.today(), shared_vars.rule_info[actuator_alias]['time_close'])
    exetime = shared_vars.rule_info[actuator_alias]['exetime']

    if time_open > time_close:
        time_close = time_close + timedelta(days=1)

    if exetime == 0:  # timer set to not set
        if shared_vars.rule_info[actuator_alias]['trigger'] is True:
            DAN.push(actuator_name, 0)
            shared_vars.rule_info[actuator_alias]['trigger'] = False
            logger.info(f'disable timer to close {actuator_alias}')
    else:
        if current > time_open and current < time_close:
            if shared_vars.rule_info[actuator_alias]['trigger'] is False:
                shared_vars.rule_info[actuator_alias]['trigger'] = True
                DAN.push(actuator_name, 1)
            shared_vars.rule_info[actuator_alias]['status'] = 'green'
            logger.info(f'timer trigger {actuator_alias}, current time: {current} rule start time: {time_open} rule end time: {time_close}')
        else:
            if shared_vars.rule_info[actuator_alias]['trigger'] is True:
                shared_vars.rule_info[actuator_alias]['trigger'] = False
                DAN.push(actuator_name, 0)
            if abs((time_open - current).total_seconds()) < 600 and time_open > current:
                shared_vars.rule_info[actuator_alias]['status'] = 'yellow'
            else:
                shared_vars.rule_info[actuator_alias]['status'] = 'red'
            logger.info(f'timer close {actuator_alias}, current time: {current} rule start time: {time_open} rule end time: {time_close}')

    return


def sensor_handler(actuator_alias, sensor_alias, order):
    actuator_name = 'Trigger' + '-I' + str(order + 1)

    # -------------Comparison with threshold--------------
    comparison_open = shared_vars.rule_info[actuator_alias]['comparison_open']
    comparison_close = shared_vars.rule_info[actuator_alias]['comparison_close']

    if comparison_open != 'notset':
        threshold_open = shared_vars.rule_info[actuator_alias]['threshold_open']
    if comparison_close != 'notset':
        threshold_close = shared_vars.rule_info[actuator_alias]['threshold_close']
    if sensor_alias not in shared_vars.df_hist_val:
        logger.info("No data pulled from IoTTalk, skip checking")
        return
    else:
        data = shared_vars.df_hist_val[sensor_alias][-1]
    # filter notset
    try:
        if 'notset' in comparison_open and 'notset' in comparison_close:
            shared_vars.rule_info[actuator_alias]['trigger'] = False
            shared_vars.rule_info[actuator_alias]['status'] = 'red'
            logger.info(f'Change all comparison to notset, close actuator {actuator_alias} and corresponding pushing thread')
            shared_vars.pushing_thread_dict[actuator_alias][1] = False
            shared_vars.pushing_thread_dict.pop(actuator_alias, None)
            to_trigger = 'NOTSET'

        elif 'notset' in comparison_open and 'notset' not in comparison_close:
            to_trigger = sensor_checker(comparison_close, threshold_close, data, 'close', actuator_name, actuator_alias, sensor_alias)

        elif 'notset' not in comparison_open and 'notset' in comparison_close:
            to_trigger = sensor_checker(comparison_open, threshold_open, data, 'open', actuator_name, actuator_alias, sensor_alias)

        else:
            to_trigger = sensor_checker(comparison_open, threshold_open, data, 'open', actuator_name, actuator_alias, sensor_alias)
            if to_trigger == 'STAY':
                to_trigger = sensor_checker(comparison_close, threshold_close, data, 'close', actuator_name, actuator_alias, sensor_alias)

        if to_trigger == 'CLOSE':
            if shared_vars.rule_info[actuator_alias]['trigger'] is True:
                DAN.push(actuator_name, 0)
            logger.info(f'sensor {sensor_alias} close {actuator_alias}, comparison: {comparison_close}, threshold: {threshold_close}, data pulled: {data}')
            shared_vars.rule_info[actuator_alias]['trigger'] = False

        elif to_trigger == 'OPEN':
            if shared_vars.rule_info[actuator_alias]['trigger'] is False:
                DAN.push(actuator_name, 1)
            logger.info(f'sensor {sensor_alias} trigger {actuator_alias}, comparison: {comparison_open}, threshold: {threshold_open}, data pulled: {data}')
            shared_vars.rule_info[actuator_alias]['trigger'] = True

        print(shared_vars.rule_info[actuator_alias]['trigger'], actuator_alias)
    except Exception as ep:
        logger.error(ep)

    return


def on_check(actuator_alias):
    sensor_alias = shared_vars.mappings[actuator_alias][0]
    order = shared_vars.mappings[actuator_alias][1]

    while shared_vars.pushing_thread_dict[actuator_alias][1]:
        if shared_vars.rule_info[actuator_alias]['rule_type'] == 'sensor':
            sensor_handler(actuator_alias, sensor_alias, order)
        else:
            time_checker(actuator_alias, sensor_alias, order)

        time.sleep(5)

    print('Pushing Thread stops')

    return
