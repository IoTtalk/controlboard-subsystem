import time
import datetime

rule = {}
prev_trigger = -10000 # duty trigger time
status = 0  # 1 for open, 0 for close


def bigger(data, threshold):
    if data is None or threshold is None: return status   #####
    if data > threshold:
        return 1
    else:
        return 0


def smaller(data, threshold):
    if data < threshold:
        return 1
    else:
        return 0


condition_handler = {
    'bigger': bigger,
    'smaller': smaller,
}


def timer_checker():
    global rule, status, prev_trigger

    current = datetime.datetime.now()
    current_epoch = time.time()
    temp_open = datetime.time(hour=rule["time_open"][0], minute=rule["time_open"][1], second=rule["time_open"][2])
    temp_close = datetime.time(hour=rule["time_close"][0], minute=rule["time_close"][1], second=rule["time_close"][2])
    time_open = datetime.datetime.combine(datetime.date.today(), temp_open)
    time_close = datetime.datetime.combine(datetime.date.today(), temp_close)

    # next day e.g. 23:00-1:00
    if time_open > time_close:
        time_close = time_close + datetime.timedelta(days=1)

    satisfied = (current > time_open and current < time_close)
    
    # if setup <10 it will not work because CB_SA.py time.sleep
    # rule["duty_pos"] + rule["duty_neg"] > 10s o.w. it will trigger line here, and line here2 will make it always red
 
    has_duty = rule["duty_pos"] != 0
 
    if not satisfied:
        status = 0
        return 0
    else:
        if has_duty:
            if prev_trigger == -10000: 
                prev_trigger = current_epoch
            elif prev_trigger + rule["duty_pos"] + rule["duty_neg"] < current_epoch: # line here
                prev_trigger = current_epoch
 
            if current_epoch - prev_trigger < rule["duty_pos"]: # line here2
                status = 1
                return 1
            else:
                status = 0
                return 0
        else:
            status = 1
            return 1
 
    '''
    duty = current_epoch < (prev_trigger + rule["duty_pos"]) \
        or current_epoch > (prev_trigger + rule["duty_pos"] + rule["duty_neg"])  # Pos -> True, Neg -> False
    if duty:
        if not satisfied:
            status = 0
            return 0
        else:
            prev_trigger = current_epoch
            status = 1
            return 1
    return 0
    '''


def sensor_checker(sensor_val):
    global rule, status, prev_trigger
    if sensor_val is None: return status   ###
    satisfied = 0  ###
    if "notset" in rule["comparison_open"] and "notset" in rule["comparison_close"]:
        status = 0
        return 0
    elif "notset" in rule["comparison_open"]:
        action = "CLOSE"
        satisfied = condition_handler[rule["comparison_close"]](sensor_val, rule["threshold_close"])

    elif "notset" in rule["comparison_close"]:
        action = "OPEN"
        satisfied = condition_handler[rule["comparison_open"]](sensor_val, rule["threshold_open"])
    else:
        satisfied = condition_handler[rule["comparison_open"]](sensor_val, rule["threshold_open"])
        action = "OPEN"
        if not satisfied:
            action = "CLOSE"
            satisfied = condition_handler[rule["comparison_close"]](sensor_val, rule["threshold_close"]) 



    current = time.time()
    has_duty = rule["duty_pos"] != 0
    if has_duty:
        duty = (current < (prev_trigger + rule["duty_pos"])) or (current > (prev_trigger + rule["duty_pos"] + rule["duty_neg"]))  # Pos -> True, Neg -> False
    else:
        duty = True
    if duty:
        if action == "CLOSE" and satisfied:
            status = 0    ###
        elif action == "OPEN" and satisfied:
            prev_trigger = current
            status = 1   ###
    
    return status  ###


def run(*args):
    # -10000 -> Open, -10001 -> Close
    global rule, status, prev_trigger
    data = args[0]
    if "mode" in data:
        rule = data
    if "sensor_val" not in data or data["sensor_val"] is None:
        if rule["mode"] == "Sensor":
            if status: return 1 - 10001   ###
            else:  -10001   ###

    if rule["mode"] == "ON":
        status = 1
        return -10000
    elif rule["mode"] == "OFF":
#        if status: return 1 - 10001   ###
#        else:  -10001   ###
        status = 0
        return -10001
    else:
        weekdays = [int(x) for x in rule["weekday"].split(",")] if len(rule["weekday"]) else list()
        if len(weekdays) == 0 or (datetime.datetime.today().weekday() in weekdays) or 7 in weekdays:
            if rule["mode"] == "Sensor":
                return sensor_checker(data["sensor_val"]) - 10001
            elif rule["mode"] == "Timer":
                return timer_checker() - 10001
        else:
            status = 0
            return -10001
