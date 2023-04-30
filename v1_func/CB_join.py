import time
import datetime

rule = {}
status = 0  # 1 for open, 0 for close
sensor_prev_status = [] # list of each sensor prev index (0 or 1)

# update
# determine
# reset

# [1,-1]
# prev status [0,0] <-- add global
# => [1, 0] -> and or 

# ON / OFF -> reset [0,0]

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

def sensor_checker(sen_data): #ver2
    ''' 
    Rule checker for each sensor condition.
    
    Args: for example, 
            sen_data = {
                "sensor_id": 9,
                "sensor_alias": "Geolocation",
                "sensor_df": "Geolocation",
                "sensor_index": 538,
                "threshold_open": 30.0,
                "threshold_close": 60.0,
                "comparison_open": "smaller",
                "comparison_close": "bigger",
                "cbelement": 3,
                "sensor_value": 29.671857294070392,
                'operation': 'AND', 
                'is_show_operation': False
            }

    Returns: this_sen_status = -1, default, means both not set or both not satisfied, keep status
                             =  0, false for this sensor
                             =  1, true for this sensor        
    '''
    this_sen_status = -1 # default -1 means not set, keep status

    if "sensor_value" not in sen_data or sen_data["sensor_value"] is None: # if no sensor value
        return this_sen_status # -1, keep status
    
    if sen_data["comparison_open"] == "notset" and sen_data["comparison_close"] == "notset": # both not set
        this_sen_status = -1 # keep status
    elif sen_data["comparison_open"] == "notset": # set close
        satisfied = condition_handler[sen_data["comparison_close"]](sen_data["sensor_value"], sen_data["threshold_close"])
        if satisfied:
            this_sen_status = 0 # false
    elif sen_data["comparison_close"] == "notset": # set open
        satisfied = condition_handler[sen_data["comparison_open"]](sen_data["sensor_value"], sen_data["threshold_open"])
        if satisfied:
            this_sen_status = 1 # true
    else: # both set
        satisfied_open = condition_handler[sen_data["comparison_open"]](sen_data["sensor_value"], sen_data["threshold_open"])
        satisfied_close = condition_handler[sen_data["comparison_close"]](sen_data["sensor_value"], sen_data["threshold_close"])
        
        # no need to handle both satisfied, since it will contradict
        if not satisfied_open and not satisfied_close:
            return this_sen_status # -1, keep status
        elif satisfied_open:
            this_sen_status = 1 # true
        elif satisfied_close:
            this_sen_status = 0 # false

    return this_sen_status

def sensor_checker_v1(sensor_val):
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

def op_cal(a, op_str, b):
    '''
    a operation b 
    
    Args: a op_str b => a operation b, (eg. a "AND" b),
          a,b will be 0 / 1

    Returns: 0, false
             1, true 
    
    '''
    if op_str == "AND":
        return (a and b)
    else: # op_str == "OR"
        return (a or b)


# def sensor_do_op(sensor_check_list, op_list): #old version
#     ans = -1 # keep status
#     for i in range(len(sensor_check_list)):
#         if i == 0:
#             prev_op = "OR"
#         else:
#             prev_op = op_list[i*2 - 1]
#         ans = op_cal(ans, prev_op, sensor_check_list[i])
#     return ans

def sensor_do_op(sensor_cur_status, op_list):
    ans = sensor_cur_status[0] # first element
    for i in range(len(sensor_cur_status)):
        if i == 0: # if is first sensor
            continue
        ans = op_cal(ans, op_list[i-1], sensor_cur_status[i])
    return ans

def run(*args):
    global rule, status, sensor_prev_status

    OpenSig = -10000  # open -> status : 1
    CloseSig = -10001 # close -> status : 0
    errorSig = 555 # error signal

    data = args[0]

    if "mode" in data:
        rule = data

    if rule["mode"] == "ON":
        sensor_prev_status.clear() # reset sensor_prev_status
        status = 1
        return OpenSig
    elif rule["mode"] == "OFF":
        sensor_prev_status.clear() # reset sensor_prev_status
        status = 0
        return CloseSig
    else: # i.e. rule["mode"] == Sensor
        all_sen_data = rule["sensors_data"]

        # initialize sensor_prev_status
        if len(sensor_prev_status) == 0: 
            for i in range(len(all_sen_data)):
                sensor_prev_status.append(0)

        # a list of senor results e.g. [0,1,-1,0], 0 for false, 1 for true, -1 for keep status
        sensor_check_list = list() 
        # operation list of all sensor data, e.g. ["AND", "OR", "AND"]
        op_list = list()
        for sen in all_sen_data:
            sensor_check_list.append(sensor_checker(sen))
            if sen["is_show_operation"] == True:
                op_list.append(sen["operation"])

        if len(sensor_check_list) != len(sensor_prev_status): # easy check if there is data lost
            return errorSig 

        # sensor_check_list = [1, -1], sensor_prev_status = [0,0] -> generate sensor_cur_status 
        sensor_cur_status = []
        for i in range(len(sensor_check_list)):
            if sensor_check_list[i] == -1: # read sensor prev status
                sensor_cur_status.append(sensor_prev_status[i])
            else: # recover by sensor cur status
                sensor_cur_status.append(sensor_check_list[i])

        sensor_prev_status = sensor_cur_status # update sensor_prev_status for next time use

        # easy check if there is data lost 
        if len(op_list) != (len(sensor_cur_status) - 1):
            return errorSig 

        sensor_after_op_ans = sensor_do_op(sensor_cur_status, op_list) # 0 or 1
        if sensor_after_op_ans == 0:
            status = 0
            return CloseSig
        else: # sensor_after_op_ans == 1
            status = 1
            return OpenSig

        '''
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
        '''