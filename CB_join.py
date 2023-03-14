import time
import datetime

rule = {}
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


def sensor_checker(sensor_val):
    global rule, status
    
    if "notset" in rule["comparison_open"] and "notset" in rule["comparison_close"]: # both not set
        status = 0
    elif "notset" in rule["comparison_open"]: # set close
        satisfied = condition_handler[rule["comparison_close"]](sensor_val, rule["threshold_close"])
        if satisfied:
            status = 0 # close
    elif "notset" in rule["comparison_close"]: # set open
        satisfied = condition_handler[rule["comparison_open"]](sensor_val, rule["threshold_open"])
        if satisfied:
            status = 1 # open
    else: # both set
        satisfied_open = condition_handler[rule["comparison_open"]](sensor_val, rule["threshold_open"])
        satisfied_close = condition_handler[rule["comparison_close"]](sensor_val, rule["threshold_close"])
        
        # no need to handle both satisfied, since it will contradict
        if not satisfied_open and not satisfied_close:
            return status # keep status
        elif satisfied_open:
            status = 1
        elif satisfied_close:
            status = 0

    return status


def run(*args):
    global rule, status

    OpenSig = -10000  # open -> status : 1
    CloseSig = -10001 # close -> status : 0

    data = args[0]

    if "mode" in data:
        rule = data

    if rule["mode"] == "ON":
        status = 1
        return OpenSig
    elif rule["mode"] == "OFF":
        status = 0
        return CloseSig
    else: # i.e. rule["mode"] == Sensor
        if "sensor_val" not in data or data["sensor_val"] is None:
            # keep status
            if status: 
                return OpenSig
            else:  
                return CloseSig
        else:
            sensor_valid = sensor_checker(data["sensor_val"])
            if sensor_valid:
                status = 1
                return OpenSig
            else:
                status = 0
                return CloseSig