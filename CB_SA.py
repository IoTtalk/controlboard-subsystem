import time
import uuid
import datetime
import os
import math
import requests
from collections import deque

import zmq


import zmq


from pony import orm


import DAN


class AG_SA():
    def __init__(self, sa_id, config, mac_addr, sa_name):
        '''
        Initialization of a CB_SA

        Args:
            sa_id: ID of this CB_SA from Database.
            sa_name: Name of this CB_SA.
            mac_addr: Mac address of this SA.
            config: Infomation for connecting to Subsystem, should contain IP, port, username, password.

        Instance variables:
            sa_id: ID for this SA, used in Database querying.
            df_hist_val: History values of sensors manipulated by this SA.
            config: Database config containing the following information.
                host: IP address of the database.
                port: Port of the database.
                user: Account provided to connect the database.
                pwd: Password provided to connect the database.
                dbname: Which Database to use.
            cb_db: Database session for this SA.
            mac_addr: Mac address of this SA.
            default_rule: basic default rule settings.

            checking: timestamp of when sensor value is acquired during outlier-based test
            initial: a list of initial sensor value (during each outlier-based test)
            ascent: a list of changes of sensor value (during each outlier-based test)
            time_on: a list of the duration of actuator being turned on (during each time-threshold test)
            prev_time: the most recent timestamp of turning on actuator (during each time-threshold test)
            prev_status: the previous status of sensor
            erlang: (lambda, n), parameters of an erlang distribution
            threshold_time: the threshold time of the sensor
            last_timestamp: the timestamp of control channel message

        Returns:
            None
        '''
        self.df_hist_val = dict()
        self.sa_id = int(sa_id)
        self.config = config
        self.cb_db = orm.Database()

        self.checking = dict()
        self.initial = dict()
        self.ascent = dict()
        self.time_on = dict()
        self.prev_time = dict()
        self.prev_status = dict()
        self.erlang = dict()
        self.threshold_time = dict()
        self.last_timestamp = ' '
        
        
        self.calibrate = False

        if mac_addr != 'None':
            self.mac_addr = mac_addr
        else:
            self.mac_addr = str(uuid.uuid4())

        self.default_rules = {{
            "threshold_open": 0.,
            "threshold_close": 0,
            "comparison_open": "notset",
            "comparison_close": "notset",
            "time_open": datetime.time(0, 0, 0),
            "time_close": datetime.time(0, 0, 0),
            "sensor_index": 0,
            "duty_pos": 0,
            "duty_neg": 0,
            "weekday": ""
        }}

        self.condition_handler = {{
            'bigger': self.bigger,
            'smaller': self.smaller,
            'biggerandequal': self.bigger_equal,
            'smallerandequal': self.smaller_equal
        }}

        ctlboard_profile = {{
            "d_name": str(sa_id) + "-" + sa_name + ".Controlboard",
            "dm_name": "ControlBoard",
            "u_name": "yb",
            "is_sim": False,
            "df_list": ["Threshold-O1", "Trigger-I1", "Threshold-O2", "Trigger-I2",
                        "Threshold-O3", "Trigger-I3", "Threshold-O4", "Trigger-I4",
                        "Threshold-O5", "Trigger-I5"]
        }}
        context = zmq.Context()
        self.socket = context.socket(zmq.PUB)
        self.socket.connect(f"tcp://{{config['host_zmq']}}:{{config['port_zmq']}}")
        self.socket.send(b"hello world")

        DAN.profile = ctlboard_profile
        DAN.device_registration_with_retry(f'http://{{config["iottalk_server"]}}:9999', self.mac_addr)

        class UserRule(self.cb_db.Entity):
            rule_id = orm.PrimaryKey(int, auto=True)  # For AG_SA to write status.
            actuator_alias = orm.Required(str)  # Alias of the actuator in this rule
            actuator_df = orm.Required(str)  # Device Feature Name of the actuator in this rule.
            sensor_alias = orm.Optional(str)  # Alias of the actuator in this rule, required if rule_type is 'sensor'.
            sensor_df = orm.Optional(str)  # Device Feature Name of sensors in this rule.
            sensor_index = orm.Optional(int)  # Which Sensor this rule is using currently.
            df_order = orm.Required(int)  # Which IDF/ODF pair to pull/push data.
            threshold_open = orm.Optional(float)  # Sensor value to decide trigger actuator or not.
            threshold_close = orm.Optional(float)  # Sensor value to decide close actuator or not.
            comparison_open = orm.Optional(str)  # Comparison method to decide trigger actuator or not.
            comparison_close = orm.Optional(str)  # Comparison method to decide close actuator or not.
            time_open = orm.Optional(datetime.time)  # Trigger actuator every when current time exceeds time_open.
            time_close = orm.Optional(datetime.time)  # Close actuator every when current time exceeds time_open.
            mode = orm.Required(str)
            weekday = orm.Optional(str)  # Weekdays this rule should be executed.
            duty_pos = orm.Optional(int)  # Positive edge of Duty Cycle.
            duty_neg = orm.Optional(int)  # Negative edge of Duty Cycle.
            sa = orm.Required("CB_SA")  # which SA it belongs to

        class CB(self.cb_db.Entity):
            cb_id = orm.PrimaryKey(int, auto=True)
            cb_name = orm.Required(str)
            sa_set = orm.Set("CB_SA", cascade_delete=True)
            account_set = orm.Set("CB_Account")  # accounts that can access this SA.
            icon = orm.Required(str)

        class CB_SA(self.cb_db.Entity):
            sa_id = orm.PrimaryKey(int, auto=True)  # id of this SA.
            sa_name = orm.Required(str)  # User-defined cb_name. Can be repeated.
            pinned = orm.Required(bool)  # if this SA is pinned.
            cb = orm.Required(CB)  # which CB this SA belongs to.
            ag_token = orm.Required(orm.LongStr)  # AG-returned token
            mac_addr = orm.Required(orm.LongStr)  # Mac-addr of this SA
            rule_set = orm.Set(UserRule, cascade_delete=True)
            p_id = orm.Required(int)  # project id of this SA
            do_id = orm.Required(str)  # device object id for this SA.

        class CB_Account(self.cb_db.Entity):
            account = orm.Required(str)  # Account of this user.
            privilege = orm.Required(int)  # User level of this user.
            cb_set = orm.Set("CB")  # CBs this user can see.


        class Outlier(self.cb_db.Entity):
            data_prio = orm.PrimaryKey(int, auto=True)
            sensor = orm.Required(str)
            initial_data = orm.Required(float)
            ascent = orm.Required(float)
            said = orm.Required(int)
            
        class Time_Threshold(self.cb_db.Entity):
            data_prio = orm.PrimaryKey(int, auto=True)
            sensor = orm.Required(str)
            time_on = orm.Required(float)
            said = orm.Required(int)

    def connect_db(self):
        '''
        Connect to correspoinding database

        Args:
            config: Database config recorded in self, containing
                host: IP address of the database.
                port: Port of the database.
                user: Account provided to connect the database.
                pwd: Password provided to connect the database.
                dbname: Which Database to use.

        Returns:
            subsystem_db: connected db session of the database recorded in self.
        '''
        retry_times = 0
        if self.config['database'] == 'sqlite':
            self.cb_db.bind(
                provider='sqlite',
                filename='cb_db.sqlite',
                create_db=True
            )
        else:
            self.cb_db.bind(
                provider='mysql',
                host=self.config['host_db'],
                user=self.config['user'],
                passwd=self.config['pwd'],
                db=self.config['dbname'],
                port=int(self.config['port_db'])
            )

        while (retry_times < 3):
            try:
                self.cb_db.generate_mapping(create_tables=True)
                break
            except orm.dbapiprovider.InternalError:
                self.cb_db.disconnect()
                retry_times += 1
        return

    @orm.db_session
    def recover(self):
        '''
        Recover SA UserRules from Database &
        generate mappings of (actuator, sensor) of IoTTalk GUI.

        Args: None.

        Returns: True or False
            True: Recover succeeded.
            False: Recover failed.
        '''
        self.status = dict()
        self.rules = dict()
        DAN.state = "RESUME"
        print("print sa's rules")
        for rule in self.cb_db.CB_SA[self.sa_id].rule_set:
            self.status[rule.rule_id] = {{
                "prev_trigger": -10000,  # An apparently impossible number.
                "status": "GREEN",  # RED / YELLOW / GREEN
                "value": 0,  # Current value of the selected sensor.
                "rule_id": rule.rule_id  # rule_id of this status recorder.
            }}
            self.rules[rule.df_order] = rule.to_dict()
            DAN.push("Trigger-I" + str(rule.df_order), 0)
        print("recovered rules:", self.rules)
        print("status recorder: ", self.status)
        self.p_id = self.cb_db.CB_SA[self.sa_id].p_id
        return

    def check_rules(self):
        '''
        Rule checker for all rules of this SA.
        Iteratively executed to generate status and open / close actuators.

        Args:
            None

        Returns:
            None
        '''

        for df_order, rule in self.rules.items():
            status = self.status[rule["rule_id"]]
            actuator_df = "Trigger-I" + str(df_order)
            sensor_df = "Threshold-O" + str(df_order)
            data = DAN.pull(sensor_df)
            if data is None:
                print("No sensor data pulled")
            else:
                candidate_sensors = rule["sensor_alias"].split(",")
                if len(candidate_sensors) == 1:
                    data = data[0]
                else:
                    data = data[0][self.rules[df_order]["sensor_index"]]
            status["value"] = data if data is not None else 0
            if rule["mode"] == "ON":
                if status["status"] != "RED":
                    status["status"] = "RED"
                    DAN.push(actuator_df, 1)
            elif rule["mode"] == "OFF":
                if status["status"] == "RED":
                    status["status"] = "GREEN"
                    DAN.push(actuator_df, 0)
            # auto mode
            else:
                weekdays = [int(x) for x in rule["weekday"].split(",")] \
                    if len(rule["weekday"]) else list()
                if len(weekdays) == 0 or (datetime.datetime.today().weekday() in weekdays) or 7 in weekdays:
                    if rule["mode"] == "Sensor" and data is not None:
                        self.sensor_checker(df_order, data)
                    else:
                        self.timer_checker(df_order)
                else:
                    if status["status"] == "RED":
                        status["status"] = "GREEN"
                        DAN.push(actuator_df, 0)
            self.success = None
            self.calibration_checker(
                rule["sensor_alias"], rule["mode"], status["status"], df_order, self.sa_id, data
            )
            if self.calibrate is True:
                status["calibrate"] = True
            else:
                status["calibrate"] = False
            status["success"] = self.success
            self.socket.send_json(status)

        return
    
    @orm.db_session
    def calibration_checker(self, sensor, mode, status, df_order, sa_id, data):
        '''
        Calibration checker for all sensors of this SA.
        Detects sensor failure with outlier-based test and time-threshold-based test.

        Args:
            sensor: sensor name
            mode: Sensor or Timer
            status: the status of the actuator corresponding to the sensor
            df_order: the mapping order of sensor and actuator
            sa_id: the id of this SA
            data: data of this sensor

        Returns:
            None
        '''
        #outlier based
        if status == 'RED':
            if sensor not in self.checking:
                if data is not None:
                    # print('SAVE SENSOR DATA FOR CHECKING')
                    self.checking[sensor] = datetime.datetime.now()
                    if sensor not in self.initial:
                        self.initial[sensor] = deque(maxlen=50)
                    self.initial[sensor].append(data)
            else:
                if self.checking[sensor] == 0:
                    if data is not None:
                        self.checking[sensor] = datetime.datetime.now()
                        if sensor not in self.initial:
                            self.initial[sensor] = deque(maxlen=50)
                        self.initial[sensor].append(data)
        
        if sensor in self.checking:
            if self.checking[sensor] != 0:
                time = datetime.datetime.now() - self.checking[sensor] 
                if time.total_seconds() > 14:
                    # print('SAVE DATA TO DATABASE')
                    if data is not None:
                        ascents = round( (data-self.initial[sensor][-1]), 3)
                        if self.calibrate == False:
                            if sensor not in self.ascent:
                                self.ascent[sensor] = deque(maxlen=50)
                            self.ascent[sensor].append(ascents)
                            self.outlier_test(sensor, self.initial[sensor][-1], ascents, sa_id)
                        self.checking[sensor] = 0
                    else:
                        pass
        
        # threshold based
        if mode == 'Sensor' and status == 'RED':
            if sensor not in self.prev_time:
                self.prev_time[sensor] = datetime.datetime.now()
                if sensor not in self.prev_status:
                    self.prev_time[sensor] = datetime.datetime.now()
                    self.prev_status[sensor] = 1
                elif self.prev_status[sensor] == 0:
                    self.prev_time[sensor] = datetime.datetime.now()
                    self.prev_status[sensor] = 1
            elif sensor in self.prev_status:
                if self.prev_status[sensor] == 0:
                    self.prev_time[sensor] = datetime.datetime.now()
                    self.prev_status[sensor] = 1
        elif mode == 'Sensor' and status == 'GREEN':
            if sensor in self.prev_status:
                if self.prev_status[sensor] == 1:
                    time_diff = datetime.datetime.now() - self.prev_time[sensor]
                    time_diff = time_diff.total_seconds()
                    if sensor not in self.time_on:
                        self.time_on[sensor] = deque(maxlen=50)
                    self.time_on[sensor].append(time_diff)
                    self.prev_status[sensor] = 0
                    
                    if self.calibrate == False:
                        self.threshold_test(sensor, time_diff, sa_id)
        else:
            self.prev_status[sensor] = 0
        if self.calibrate is True:
            self.calib_complete_check(sensor)
        return
    
    def threshold_test(self, sensor, time_diff, sa_id):
        # do the calculation with given data
        if sensor not in self.threshold_time:
            try:
                histogram_bins = dict()
                find_medium = 0
                medium = -1
                actime = self.time_on[sensor]
                for act in actime:
                    act = math.floor(act / 60 / 2)
                    if act not in histogram_bins:
                        histogram_bins[act] = 1
                    else:
                        histogram_bins[act] += 1
                for bins in histogram_bins:
                    histogram_bins[bins] = histogram_bins[bins] / len(actime)
                    find_medium += histogram_bins[bins]
                    if(find_medium >= 0.5 and medium == -1): medium = float(bins)*2+1
                # find the erlang distribution function that fits this histogram find lambda and n
                # y = rate = histogram bins output, act = time(t)
                # E[t] is the middle value in this histogram
                # save the time which has error of < 0.001 into threshold_time[sensor]
                least_error = 0
                for n in range(3,7):
                    error = 0
                    for lam in range(0, 100):
                        l = float(lam)/100
                        for bins in histogram_bins:
                            t = float(bins)*2+1
                            ft = ((l**n) * t**(n-1) * math.exp((-1)*l*t)) / math.factorial(n-1) 
                            error += abs(ft - histogram_bins[bins])
                        if least_error == 0: 
                            least_error = error
                            self.erlang[sensor] = (l, n)
                        elif least_error > error:
                            least_error = error
                            self.erlang[sensor] = (l, n)
                # found best lambda and n
                # erlang[sensor][0] = lambda   erlang[sensor][1] = n
                l = self.erlang[sensor][0]
                n = self.erlang[sensor][1]
                for t in range(int(medium), 60):
                    pr = 0
                    for i in range(1, n):
                        pr += (l**i * t**i * math.exp((-1)*l*t))/math.factorial(i)
                    if pr <= 0.001:
                        self.threshold_time[sensor] = t
                        break
                if sensor not in self.threshold_time: self.threshold_time[sensor] = 60
            except Exception as e:
                print('arithmatic error')
                print(e)
        if sensor in self.threshold_time:
            if time_diff > self.threshold_time[sensor]*60: 
                self.calib_request(sensor)
                print('begin sensor calibration (from time)')
                self.calibrate = True
            else:
                print('sensor normal (from time)')
        return 
    
    def outlier_test(self, sensor, initial_data, ascent, sa_id):
        # do calculation for MSE here
        if( len(self.initial[sensor]) == 50):
            x_avg = sum(self.initial[sensor]) / len(self.initial[sensor])
            y_avg = sum(self.ascent[sensor]) / len(self.ascent[sensor])
            x_mse = 0
            y_mse = 0
            xy_mse = 0
            for i in range(len(self.initial[sensor])):
                x_mse += (self.initial[sensor][i] - x_avg) ** 2
                y_mse += (self.ascent[sensor][i] - y_avg) ** 2
                xy_mse += (self.initial[sensor][i] - x_avg) * (self.ascent[sensor][i] - y_avg)

            sample_size = len(self.initial[sensor])
            # calculate the regression model and calculate m first
            rate = 0
            try:
                m = xy_mse / x_mse
                b = y_avg - m * x_avg
                error = ascent - m * initial_data - b

                sigma_square = ( y_mse - m * xy_mse ) / (sample_size - 2)
                sigma = math.sqrt ( sigma_square )

                rate_denom = ( 1 - 1/sample_size - (initial_data - x_avg)**2 / x_mse)
                rate = ( error / sigma ) / math.sqrt( rate_denom )

                rate_change = (sample_size-3)/(sample_size-2-rate**2)
                rate = rate * math.sqrt(rate_change)
            except Exception as e:
                print('arithmatic error')
                print(e)
            
            if abs(rate) > 2: 
                self.calib_request(sensor) # error detected
                print('begin sensor calibration')
                self.calibrate = True
            else:
                print('sensor normal')
                pass
        return
    
    def calib_request(self, sensor):
        # call this when the tests are not passed
        try:
            # DAN.calibrate(self.cb_db.CB_SA[self.cb_id].p_id)
            r = requests.Session().post(
                f'http://{{self.config["iottalk_server"]}}:9999/calibrate_sensor',
                json={{'sensor': sensor, 'p_id': self.p_id, 'state': None}}, 
                timeout=10
            )
            pass
        except Exception as e:
            print("calibration request error: ")
            print(e)
        return
    
    def calib_complete_check(self, sensor):
        # under calibration mode, keep checking for DA's return message
        try:
            msg = DAN.pull('__Ctl_O__')
            if msg != []:
                if self.last_timestamp == msg[0][0]: continue
                self.last_timestamp = msg[0][0]
                msg = msg[0][1]
                if len(msg) == 3:
                    if msg[2] is 'done':
                        # report to user calibration done
                        self.checking[sensor] = 0
                        self.calibrate = False
                        self.success = True
                        pass
                    elif msg[2] is 'failed':
                        # report to user calibration failed
                        self.checking[sensor] = 0
                        self.calibrate = False
                        self.success = False
                        pass
                    else:
                        pass
        except Exception as e:
            print("Pull control message error: ")
            print(e)
        return
    

    def timer_checker(self, df_order):
        """
        Timer-type rule checking handler. Push to IoTTalk server accordingly.

        Args:
            df_order: The IDF/ODF pair of ControlBoard to pull/push data.

        Returns:
            None
        """
        rule = self.rules[df_order]
        status = self.status[rule["rule_id"]]

        current = datetime.datetime.now()
        current_epoch = time.time()
        actuator_df = "Trigger-I" + str(df_order)
        time_open = datetime.datetime.combine(datetime.date.today(), rule["time_open"])
        time_close = datetime.datetime.combine(datetime.date.today(), rule["time_close"])

        if time_open > time_close:
            time_close = time_close + datetime.timedelta(days=1)

        satisfied = (current > time_open and current < time_close)
        about2trigger = (abs((time_open - current).total_seconds()) < 600 and time_open > current)
        duty = current_epoch < (status["prev_trigger"] + rule["duty_pos"]) \
            or current_epoch > (status["prev_trigger"] + rule["duty_pos"] + rule["duty_neg"])  # Pos -> True, Neg -> False
        try:
            if duty:
                if status["status"] == "RED":
                    if satisfied:
                        pass
                    else:
                        DAN.push(actuator_df, 0)
                        status["status"] = "GREEN"
                elif status["status"] == "YELLOW":
                    if satisfied:
                        DAN.push(actuator_df, 1)
                        status["status"] = "RED"
                        status["prev_trigger"] = current_epoch
                    elif about2trigger:
                        status["status"] = "YELLOW"
                    else:
                        status["status"] = "GREEN"
                elif status["status"] == "GREEN":
                    if satisfied:
                        DAN.push(actuator_df, 1)
                        status["status"] = "RED"
                        status["prev_trigger"] = current_epoch
                    elif about2trigger:
                        status["status"] = "YELLOW"
                    else:
                        status["status"] = "GREEN"
            else:
                if status["status"] == "RED":
                    DAN.push(actuator_df, 0)
                status["status"] = "GREEN"
        except Exception as err:
            print(err)
        return

    def sensor_checker(self, df_order, data):
        """
        Sensor-type rule checking handler. Push to IoTTalk server accordingly.

        Args:
            df_order: The IDF/ODF pair of ControlBoard to pull/push data.
            data: Pulled data.

        Returns:
            None
        """
        rule = self.rules[df_order]
        print("Data received:", data)
        sensor_alias = rule["sensor_alias"].split(",")[rule["sensor_index"]]
        status = self.status[rule["rule_id"]]
        status["value"] = data
        if sensor_alias not in self.df_hist_val:
            self.df_hist_val[sensor_alias] = list()
        self.df_hist_val[sensor_alias].append(data)
        actuator_df = "Trigger-I" + str(df_order)
        try:
            avg = sum(self.df_hist_val[sensor_alias]) / len(self.df_hist_val[sensor_alias])
            if "notset" in rule["comparison_open"] and "notset" in rule["comparison_close"]:
                if status["status"] == "RED":
                    DAN.push(actuator_df, 0)
                status["status"] = "GREEN"
                return
            elif "notset" in rule["comparison_open"]:
                action = "CLOSE"
                satisfied, next_action = self.condition_handler[rule["comparison_close"]](data, rule["threshold_close"], avg)
            elif "notset" in rule["comparison_close"]:
                action = "OPEN"
                satisfied, next_action = self.condition_handler[rule["comparison_open"]](data, rule["threshold_open"], avg)
            else:
                satisfied, next_action = self.condition_handler[rule["comparison_open"]](data, rule["threshold_open"], avg)
                action = "OPEN"
                if not satisfied:
                    action = "CLOSE"
                    satisfied, next_action = self.condition_handler[rule["comparison_close"]](data, rule["threshold_close"], avg)
            current = time.time()
            has_duty = rule["duty_pos"] != 0
            if has_duty:
                duty = (current < (status["prev_trigger"] + rule["duty_pos"])) or (current > (status["prev_trigger"] + rule["duty_pos"] + rule["duty_neg"]))  # Pos -> True, Neg -> False
            else:
                duty = True
            if duty:
                if status["status"] == "RED":
                    if action == "CLOSE":
                        if satisfied:
                            DAN.push(actuator_df, 0)
                            if next_action == "YELLOW":
                                status["status"] = "YELLOW"
                            else:
                                status["status"] = "GREEN"
                elif status["status"] == "GREEN":
                    if action == "OPEN":
                        if satisfied:
                            DAN.push(actuator_df, 1)
                            status["status"] = "RED"
                            status["prev_trigger"] = current
                        else:
                            if next_action == "YELLOW":
                                status["status"] = "YELLOW"
                else:
                    if action == "OPEN":
                        if satisfied:
                            DAN.push(actuator_df, 1)
                            status["status"] = "RED"
                            status["prev_trigger"] = current
                        else:
                            if next_action != "YELLOW":
                                status["status"] = "GREEN"
                    else:
                        if next_action != "YELLOW":
                            status["status"] = "GREEN"
            else:
                if status["status"] == "RED":
                    DAN.push(actuator_df, 0)
                status["status"] = "GREEN"
            return
        except Exception as err:
            print(err)

    @staticmethod
    def bigger(data, threshold, avg):
        """
        Check if data > threshold. Return comparison results as boolean, string.

        Args:
            data: data pulled from IoTTalk server.
            threshold: threshold settings from rule_info in memory.
            avg: the average of history data stored in memory.

        Returns:
            satisfied: True/False, whether the rule is satisfied by arg data
            status: RED/YELLOW/UNCHANGED, Card status in UI.
        """
        if data > threshold:
            satisfied = True
            status = 'RED'
        else:
            satisfied = False
            print('bigger', 0.78 * (threshold - avg) + avg)
            if data > 0.78 * (threshold - avg) + avg:
                status = 'YELLOW'
            else:
                status = 'UNCHANGED'

        return satisfied, status

    @staticmethod
    def smaller(data, threshold, avg):
        """Check if data < threshold. Return comparison results as boolean, string.

        Args:
            data: data pulled from IoTTalk server.
            threshold: threshold settings from rule_info in memory.
            avg: the average of history data stored in memory.

        Returns:
            satisfied: whether the rule is satisfied by arg data
            status: Card status in UI.
        """
        if data < threshold:
            satisfied = True
            status = 'RED'
        else:
            satisfied = False
            print('smaller', 0.22 * (avg - threshold) + threshold)
            if data < 0.22 * (avg - threshold) + threshold:
                print(data, 'yellow')
                status = 'YELLOW'
            else:
                status = 'UNCHANGED'
        return satisfied, status

    @staticmethod
    def bigger_equal(data, threshold, avg):
        """Check if data >= threshold. Return comparison results as boolean, string.

        Args:
            data: data pulled from IoTTalk server.
            threshold: threshold settings from rule_info in memory.
            avg: the average of history data stored in memory.

        Returns:
            satisfied: whether the rule is satisfied by arg data
            status: Card status in UI.
        """
        if data >= threshold:
            satisfied = True
            status = 'RED'
        else:
            print('biggerequal', 0.78 * (threshold - avg) + avg)
            satisfied = False
            if data > 0.78 * (threshold - avg) + avg:
                status = 'YELLOW'
            else:
                status = 'UNCHANGED'

        return satisfied, status

    @staticmethod
    def smaller_equal(data, threshold, avg):
        """Check if data <= threshold. Return comparison results as boolean, string.

        Args:
            data: data pulled from IoTTalk server.
            threshold: threshold settings from rule_info in memory.
            avg: the average of history data stored in memory.

        Returns:
            satisfied: whether the rule is satisfied by arg data
            status: Card status in UI.
        """
        if data <= threshold:
            satisfied = True
            status = 'RED'
        else:
            satisfied = False
            print('smallerequal', 0.22 * (avg - threshold) + threshold)
            if data < 0.22 * (avg - threshold) + threshold:
                status = 'YELLOW'
            else:
                status = 'UNCHANGED'
        return satisfied, status


sa = AG_SA('{sa_id}', {config}, '{mac_addr}', '{sa_name}')

sa.connect_db()
sa.recover()


while True:
    print('start checking rules')
    sa.check_rules()
    time.sleep(5)
