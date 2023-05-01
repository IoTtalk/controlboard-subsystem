from pickle import FALSE
import time
import uuid
import datetime
import zmq
import csmapi, DAN

class AG_SA():
    def __init__(self, sa_id, config, mac_addr, sa_name, rules):
        '''
        Initialization of a CB_SA

        Args:
            sa_id: ID of this CB_SA from Database.
            sa_name: Name of this CB_SA.
            mac_addr: Mac address of this SA.
            config: Infomation for connecting to Subsystem.
            rules: CBElements of this SA.

        Instance variables:
            sa_id: ID for this SA, used in Database querying.
            df_hist_val: History values of sensors manipulated by this SA.
            config: Configurations including the following information.
                iottalk_server: IP address of the IoTtalk server to register device.
                host_zmq: host of CB subsystem to send status.
                port: port of CB subsystem status collector to send status.
            mac_addr: Mac address of this SA.
            default_rule: basic default rule settings.

        Returns:
            None
        '''
        self.df_hist_val = dict()
        self.sa_id = int(sa_id)
        self.config = config
        self.rules = rules
        if mac_addr != 'None':
            self.mac_addr = mac_addr
        else:
            self.mac_addr = str(uuid.uuid4())

        ctlboard_profile = {{
            "d_name": sa_name,
            "dm_name": "ControlBoard",
            "u_name": "yb",
            "is_sim": False,
            "df_list": ["CBElement-O1", "CBElement-TI1", "CBElement-O2", "CBElement-TI2",
                        "CBElement-O3", "CBElement-TI3", "CBElement-O4", "CBElement-TI4",
                        "CBElement-O5", "CBElement-TI5", "CBElement-O6", "CBElement-TI6",
                        "CBElement-O7", "CBElement-TI7", "CBElement-O8", "CBElement-TI8",
                        "CBElement-O9", "CBElement-TI9"]
        }}
        context = zmq.Context()
        self.socket = context.socket(zmq.PUB)
        self.socket.connect(f"tcp://{{config['host_zmq']}}:{{config['port_zmq']}}")
        self.socket.send(b"hello world")

        DAN.profile = ctlboard_profile
        DAN.device_registration_with_retry(f'http://{{config["iottalk_server"]}}:9999', self.mac_addr)



        not_bind = 1
        timestamp = time.time()
        while not_bind:
            if time.time() - timestamp > 1: break
            try:
                resultCtrlO = csmapi.pull(self.mac_addr, '__Ctl_O__')
                if resultCtrlO != [] and resultCtrlO != None:
                    print('resultCtrlO:', resultCtrlO[0][1][0])
                    if resultCtrlO[0][1][0] == 'RESUME':
                        not_bind = 0
                    else:
                        time.sleep(0.05)
            except Exception as e:
                print(e)
                time.sleep(0.1)
        
        
        time.sleep(0.6) # essential! Wait for ESM project restart!



    def recover(self):
        '''
        Recover SA CBElements & generate Rule status.

        Args: None.

        Returns: None
        '''
        self.status = dict()  # diff status data for diff rule_id
        print("print sa's rules")
        for (df_order, rule) in self.rules.items():

            default_all_sensor_value = dict() # initialize all sensors value 0
            for each_sensor in rule["sensors_data"]:
                default_all_sensor_value[each_sensor["sensor_index"]] = 0
            
            rule_id = rule["rule_id"]
            self.status[rule_id] = {{
                "prev_trigger": -10000,  # for recording the first time calculating duty.
                "status": "GREEN",  # RED / YELLOW / GREEN
                "value": default_all_sensor_value,  # Current value of all selected sensor. eg. "value" : a dict with (sensor_index : sensor_value) mapping
                "rule_id": rule_id,  # rule_id of this status recorder.
                'prev_status': "NONE"  # record previous status, DAN push only if it is diff status or is "Sensor".
            }}

            # whenever we press "Save", recover each status to OFF in all cb_join
            actuator_df = "CBElement-TI" + str(df_order)
            recover_close_rule = {{
                "mode": "OFF",
            }}
            DAN.push(actuator_df, recover_close_rule)
            time.sleep(2)

        print("recovered rules:", self.rules)
        print("status recorder: ", self.status)
        return

    ############

    def is_timer_valid(self, weekday_setup, time_open_setup, time_close_setup):
        '''
        check if current time is in [time_open, time_close]

        Args:
            weekday_setup: user setup weekday open
            time_open_setup: (list of datetime.time) user setup time open
            time_close_setup: (list of datetime.time) user setup time close
            
        Returns:
            0: time condition false
            1: time condition true (time not set / in correct time)
        '''

        weekdays = [int(x) for x in weekday_setup.split(",")] if len(weekday_setup) else list()
        if len(weekdays) == 0 or (datetime.datetime.today().weekday() in weekdays) or 7 in weekdays:
            if time_open_setup == [0,0,0] and time_close_setup == [0,0,0]:
                return 1 # time not set

            current = datetime.datetime.now()
            current_epoch = time.time()
            temp_open = datetime.time(hour=time_open_setup[0], minute=time_open_setup[1], second=time_open_setup[2])
            temp_close = datetime.time(hour=time_close_setup[0], minute=time_close_setup[1], second=time_close_setup[2])
            time_open = datetime.datetime.combine(datetime.date.today(), temp_open)
            time_close = datetime.datetime.combine(datetime.date.today(), temp_close)

            # next day e.g. 23:00-1:00
            if time_open > time_close:
                time_close = time_close + datetime.timedelta(days=1)

            satisfied = (current > time_open and current < time_close)

            if satisfied:
                return 1 # time condition true
            
        return 0 # time condition false

    def is_duty_valid(self, rule_id, duty_pos, duty_neg):
        '''
        check if duty has been set, and current time is needs open/close
        Notice : if setup(pos+neg) <10 it will not work because CB_SA.py time.sleep

        Args:
            rule_id: rule id from rules item, for duty get status prev_trigger
            duty_pos: duty positive sustained time (actuator on)
            duty_neg: duty negitive sustained time (actuator off)

        Instance variables:
            status["prev_trigger"]: record the first time we start this function, and reset when duty not set
            which_cycle: to get now time is in which cycle for open/close actuator
            current_epoch: now time

        Returns:
            0: duty condition false
            1: duty condition true (duty not set / duty condition is on)
        '''

        status = self.status[rule_id]

        if duty_pos == 0:
            status["prev_trigger"] = -10000
            return 1; # duty not set
        
        current_epoch = int(time.time())

        if status["prev_trigger"] == -10000:
            status["prev_trigger"] = current_epoch

        which_cycle = (current_epoch - status["prev_trigger"]) % (duty_pos + duty_neg)
        if which_cycle <= duty_pos:
            return 1 # actuator on
        else:
            return 0 # actuator off

    def is_sensor_set(self, comparison_open_setup, comparison_close_setup, threshold_open_setup, threshold_close_setup):
        '''
        check if sensor condition has been set

        Args:
            comparison_open_setup: comparison user set for actuator on
            comparison_close_setup: comparison user set for actuator off

        Returns:
            0: sensor condition not set
            1: sensor condition set
        '''
        if comparison_open_setup == "notset" and comparison_close_setup == "notset":
            return 0
        if threshold_open_setup == 0 and threshold_close_setup == 0:
            return 0
        return 1

    def pre_processing(self, rule_id, tmp_rule): 
        '''
        to check timer and duty then create different rules to push to DAN

        Args:
            rule_id: rule id from rules item, for duty get status prev_trigger
            temp_rule: rules from below check_rules function

        Returns: #TODO change here
            pre_pro_rule: a dictionary rules may be different in each case
            # if time & duty are valid, and sensor condition has been set
                pre_pro_rule is a dict with :
                    "mode": the mode select -> ON / OFF / Sensor,
                    "sensors_data": a list of dictionary which is sorted by sensor_index of each dictionary
                                    each dict in sensors_data contains below infos
                        "sensor_id": the sensor id of CB_Sensor in CB database,
                        "sensor_alias": sensor alias name,
                        "sensor_df": sensor df name,
                        "sensor_index": sensor index of v1 which is only,
                        "threshold_open": ,
                        "threshold_close": 60.0,
                        "comparison_open": "smaller",
                        "comparison_close": "bigger",
                        "cbelement": 3,
                        "sensor_value": 29.671857294070392,
                        "operation": 'OR', 
                        "is_show_operation": True
                    
                    "threshold_open": tmp_rule["threshold_open"],
                    "threshold_close": tmp_rule["threshold_close"],
                    "comparison_open": tmp_rule["comparison_open"],
                    "comparison_close": tmp_rule["comparison_close"],
                    "mode": "Sensor",
                    "sensor_val": tmp_rule["sensor_val"]
        '''

        pre_pro_rule = {{
            "mode": tmp_rule["mode"],
        }}

        if tmp_rule["mode"] == "ON" or tmp_rule["mode"] == "OFF": # manual
            return pre_pro_rule

        if self.is_timer_valid(tmp_rule["weekday"], tmp_rule["time_open"], tmp_rule["time_close"]) == 1:
            if self.is_duty_valid(rule_id, tmp_rule["duty_pos"], tmp_rule["duty_neg"]) == 1:
                
                flag_for_sensor_has_at_least_one_set = 0
                for i in range(len(tmp_rule["sensors_data"])):
                    cur_sensor_data = tmp_rule["sensors_data"][i]
                    if self.is_sensor_set(cur_sensor_data["comparison_open"], cur_sensor_data["comparison_close"], cur_sensor_data["threshold_open"], cur_sensor_data["threshold_close"]) == 1:
                        flag_for_sensor_has_at_least_one_set = 1
                        break
                
                if flag_for_sensor_has_at_least_one_set:
                    pre_pro_rule["mode"] = "Sensor"
                    pre_pro_rule["sensors_data"] = tmp_rule["sensors_data"]
                    #pre_pro_rule["operation"] = tmp_rule["operation"]
                    return pre_pro_rule
                else: # all sensor condition not set
                    pre_pro_rule["mode"] = "ON"
                    return pre_pro_rule

        # else => time/duty invalid
        pre_pro_rule["mode"] = "OFF"
        return pre_pro_rule

    def check_rules(self): 
        '''
        Rule checker for all rules of this SA.
        Iteratively executed to generate status and open / close actuators.

        Args: None

        Returns: None
        '''
        try:
            print("self.rules.items() : ",self.rules.items())
            for df_order, rule in self.rules.items():
                status = self.status[rule["rule_id"]]
                prev_status = status["prev_status"]

                new_sensor_data = rule["sensors_data"] # to put the sensor data get from CBElement into rule

                # print("\n\nAAA status : ",status,"\n\n")
                # print("\n\nBBB rule : ",rule,"\n\n")
                actuator_df = "CBElement-TI" + str(df_order)
                sensor_df = "CBElement-O" + str(df_order)
                data = DAN.pull(sensor_df)
                '''
                data here:  # be careful here if one of the sensor is None then data will be None
                [
                    [
                        [-40.35571174163307, 'Geolocation', 'SimDev224'], 
                        [-32.51651155297341, 'Geolocation', 'SimDev230']
                    ]
                ] => sensor val list
                or
                [-10001] -> OFF / [-10000] -> ON => impoossible nums represent signal from CBElement-I
                '''
                print("\ndata : ",data,"\n")
                if data is None:
                    print("No sensor data pulled")
                else:
                    if len(data) == 1 and (data[0] == -10000 or data[0] == -10001): # if data is signal from CBElement-I
                        data[0] += 10001
                        # print("\n\n!!!!!!!!??????!!!!!!!!\n\n")
                        status["status"] = "RED" if data[0] else "GREEN" #TODO status
                        continue
                    else: # if data is sensors val list
                        if isinstance(data[0][0], list): # deal with the difference between single and multi snesor
                            data = data[0]

                        #data = data[0] 
                        for i in range(len(data)):
                            new_sensor_data[i]["sensor_value"] = data[i][0]
                            if data[i][0] is not None: # update all sensors value into status (for frontend to use)
                                status["value"][new_sensor_data[i]["sensor_index"]] = data[i][0] # if is not None, keep origin sensor value in status

                # print("-----------------\n")
                # print(status)
                
                temp_rule = {{
                    "time_open": [rule["time_open"].hour, rule["time_open"].minute, rule["time_open"].second],
                    "time_close": [rule["time_close"].hour, rule["time_close"].minute, rule["time_close"].second],
                    "mode": rule["mode"],
                    "weekday": rule["weekday"],
                    "duty_pos": rule["duty_pos"],
                    "duty_neg": rule["duty_neg"],
                    "sensors_data": new_sensor_data,
                    #"operation": rule["operation"]
                }}
                print("*" * 30)
                print("\ntemp rule : ", temp_rule)
                
                push_rule = self.pre_processing(rule["rule_id"],temp_rule)
                print("\npush_rule : ", push_rule)
                print("\nnow actuator : ", rule["actuator_alias"])

                # not pushing while no sensor condition and same status
                now_status = push_rule["mode"]
                print("now_status", now_status)
                print("prev_status", prev_status)
                if prev_status != "NONE":
                    if now_status != "Sensor" and now_status == prev_status:
                        self.socket.send_json(status) # let frontend get status
                        continue

                DAN.push(actuator_df, push_rule)

                status["prev_status"] = now_status # be aware of call by reference and call by value

                print("CCC status ", status)
                self.socket.send_json(status)
                
        except Exception as err:
            print("Checking CBElement failed, ", err)
        return

sa = AG_SA('{sa_id}', {config}, '{mac_addr}', '{sa_name}', {rules})
sa.recover()

while True:
    print('\nstart checking rules of', sa.sa_id)
    sa.check_rules()
    time.sleep(2)
