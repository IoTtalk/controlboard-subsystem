# calibration.py
import DAN
import csmapi, requests
import math
NewSession=requests.Session()

checking = dict()
initial = dict()
prev_time = dict()
prev_status = dict()
def threshold_test(sensor_alias, time_diff):
    # do the calculation with given data
    if(time_diff > 1800): 
        calib_request(sensor_alias)
    return 

def outlier_test(sensor_alias, initial_data, ascent, sample_size, x_avg, y_avg, x_mse, y_mse, xy_mse):
    # calculate the regression model and calculate m first
    m = xy_mse / x_mse
    b = y_avg - m * x_avg
    error = ascent - m * initial_data + b
    sigma = math.sqrt ( ( y_mse - m * xy_mse ) / (sample_size - 2) )
    rate = ( error / sigma ) / math.sqrt( ( 1 - 1/sample_size - (initial_data - x_avg)**2 / x_mse) )
    rate = rate * math.sqrt((sample_size-3)/(sample_size-2-rate**2))
    if abs(rate) > 2 and sample_size > 50: 
        calib_request(sensor_alias) # error detected
    return

def calib_request(sensor_alias):
    # call this when the two tests are not passed
    try:
        DAN.push('Message-I', f'start calibration {sensor_alias}')
    except Exception as e:
        print("calibration request error: ")
        print(e)
    return
    
def calib_complete_check(sensor_alias):
    # under calibration mode, keep checking for DA's return message
    try:
        msg = DAN.pull('Message-O')
        if msg is not None:
            msg = msg[0]
        if msg is 'complete' or msg is 'failed':
            checking[sensor_alias] = False
        else:
            checking[sensor_alias] = True
    except Exception as e:
        print("Pull control message error: ")
        print(e)

    try:
        if msg is 'complete':
            DAN.push('Message-I', 'not calibrating')
            pass
        elif msg is 'failed': # also need to add notification for changing sensors, using line bot or something
            DAN.push('Message-I', 'change sensor')
            pass
        else:  # msg is 'processing'
            pass
    except Exception as e:
        print("Push message to control channel error: ")
        print(e)

    return