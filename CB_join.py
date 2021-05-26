import time
import datetime

rule = {}
prev_trigger = -10000
status = 0  # 1 for open, 0 for close


def bigger(data, threshold):
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
    time_open = datetime.datetime.combine(datetime.date.today(), rule["time_open"])
    time_close = datetime.datetime.combine(datetime.date.today(), rule["time_close"])

    if time_open > time_close:
        time_close = time_close + datetime.timedelta(days=1)

    satisfied = (current > time_open and current < time_close)
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


def sensor_checker(sensor_val):
    global rule, status, prev_trigger
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
            satisfied = condition_handler[rule["comparison_close"]](data, rule["threshold_close"], avg)
    current = time.time()
    has_duty = rule["duty_pos"] != 0
    if has_duty:
        duty = (current < (prev_trigger + rule["duty_pos"])) or (current > (prev_trigger + rule["duty_pos"] + rule["duty_neg"]))  # Pos -> True, Neg -> False
    else:
        duty = True
    if duty:
        if action == "CLOSE" and satisfied:
            status = 0
            return 0
        elif action == "OPEN" and satisfied:
            prev_trigger = current
            status = 1
            return 1
    status = 0
    return 0


def run(*args):
    global rule, status, prev_trigger
    data = args[0]
    if "mode" in data:
        rule = data
        if len(rule["time_open"]):
            temp = rule["time_open"]
            rule["time_open"] = datetime.time(hour=temp[0], minute=temp[1], second=temp[2])
        if len(rule["time_close"]):
            temp = rule["time_close"]
            rule["time_close"] = datetime.time(hour=temp[0], minute=temp[1], second=temp[2])

    if "sensor_val" not in data or data["sensor_val"] is None:
        if rule["mode"] == "Sensor":
            return status

    if rule["mode"] == "ON":
        status = 1
        return 1
    elif rule["mode"] == "OFF":
        status = 0
        return 0
    else:
        weekdays = [int(x) for x in rule["weekday"].split(",")] if len(rule["weekday"]) else list()
        if len(weekdays) == 0 or (datetime.datetime.today().weekday() in weekdays) or 7 in weekdays:
            if rule["mode"] == "Sensor":
                return sensor_checker(data["sensor_val"])
            elif rule["mode"] == "Timer":
                return timer_checker()
        else:
            status = 0
            return 0
