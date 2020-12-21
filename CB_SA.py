import time
import uuid
import datetime
import os
import math
import requests

from collections import deque


import zmq


from pony import orm


import DAN


class AG_SA():
    def __init__(self, sa_id, config, mac_addr, sa_name):
        '''
        Initialization of a CB_SA

        Args:
            cb_id: ID of this CB_SA from Database.
            mappings: Mapping of actuator to sensors.
            config: Infomation for connecting to Subsystem, should contain IP, port, username, password.

        Instance variables:
            mappings: A dictionary of the following format.
            {{
                'actuator_alias': (sensor_alias, DF order on IoTTalk GUI)
            }}
            cb_id: ID for this SA, used in Database querying.
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

        Returns:
            None
        '''
        self.mappings = dict()
        self.df_hist_val = dict()
        self.cb_id = cb_id
        self.config = config
        self.cb_db = orm.Database()

        self.checking = dict()
        self.initial = dict()
        self.prev_time = dict()
        self.prev_status = dict()
        self.erlang = dict()
        self.threshold_time = dict()
        self.calibrate = False;

        if mac_addr != 'None':
            self.mac_addr = mac_addr
        else:
            self.mac_addr = str(uuid.uuid4())

        self.default_rule = {{
            'rule_type': 'sensor',
            'threshold_open': 0.,
            'threshold_close': 0,
            'comparison_open': 'notset',
            'comparison_close': 'notset',
            'mode': 'auto',
            'period': 0
        }}

        self.condition_handler = {{
            'bigger': self.bigger,
            'smaller': self.smaller,
            'biggerandequal': self.bigger_equal,
            'smallerandequal': self.smaller_equal
        }}

        ctlboard_profile = {{
            'd_name': str(cb_id) + '.Controlboard',
            'dm_name': 'ControlBoard',
            'u_name': 'yb',
            'is_sim': False,
            'df_list': ['Threshold-O1', 'Trigger-I1', 'Threshold-O2', 'Trigger-I2',
                        'Threshold-O3', 'Trigger-I3', 'Threshold-O4', 'Trigger-I4',
                        'Threshold-O5', 'Trigger-I5']
        }}
        context = zmq.Context()
        self.socket = context.socket(zmq.PUB)
        self.socket.connect("tcp://140.113.215.12:7790")
        self.socket.send(b"hello world")

        DAN.profile = ctlboard_profile
        DAN.device_registration_with_retry(f'http://{{config["iottalk_server"]}}:9999', self.mac_addr)

        class UserRule(self.cb_db.Entity):
            rule_id = orm.PrimaryKey(int, auto=True)  # For AG_SA to write status.
            rule_type = orm.Required(str)  # Sensor / Timer.
            actuator_alias = orm.Required(str)  # Alias of the actuator in this rule.
            sensor_alias = orm.Required(str)  # Alias of the actuator in this rule, required if rule_type is 'sensor'.
            threshold_open = orm.Optional(float)  # Sensor value to decide trigger actuator or not.
            threshold_close = orm.Optional(float)  # Sensor value to decide close actuator or not.
            comparison_open = orm.Optional(str)  # Comparison method to decide trigger actuator or not.
            comparison_close = orm.Optional(str)  # Comparison method to decide close actuator or not.
            time_open = orm.Optional(datetime.time)  # Trigger actuator every when current time exceeds time_open.
            time_close = orm.Optional(datetime.time)  # Close actuator every when current time exceeds time_open.
            exetime = orm.Optional(int)  # execution time for periodically execution
            period = orm.Required(int)  # Period functionality.
            mode = orm.Required(str)
            sa = orm.Required("CB_SA")  # which SA it belongs to

        class CB(self.cb_db.Entity):
            cb_id = orm.PrimaryKey(int, auto=True)
            cb_name = orm.Required(str)
            sa_set = orm.Set("CB_SA", cascade_delete=True)
            shared = orm.Required(bool)
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
            path = os.path.join(os.getcwd(), 'cb_db.sqlite')
            print(path)
            self.cb_db.bind(
                provider='sqlite',
                filename=path,
                create_db=True
            )
        else:
            self.cb_db.bind(
                provider='mysql',
                host=self.config['host'],
                user=self.config['user'],
                passwd=self.config['pwd'],
                db=self.config['dbname'],
                port=int(self.config['port'])
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
        # Pulling Alias
        DAN.state = "RESUME"
        self.status = dict()
        while len(self.mappings) == 0:
            alias_in = DAN.get_alias('Threshold-O' + str(1))
            alias_out = DAN.get_alias('Trigger-I' + str(1))
            print('Please bind first')

            i = 1
            while len(alias_in):
                try:
                    if 'Threshold' not in alias_in[0] and 'Trigger' not in alias_out[0]:
                        alias_in = alias_in[0].replace('-O', '')
                        alias_out = alias_out[0].replace('-I', '')
                        self.mappings[alias_out] = (alias_in, i)
                        self.status[alias_in] = {{
                            'cb_id': self.cb_id,
                            'status': 'RED',
                            'prev_trigger': -10000,
                            'value': 0
                        }}
                        self.df_hist_val[alias_in] = deque(maxlen=200)
                        self.socket.send_json(self.status[alias_in])
                    i += 1
                    alias_in = DAN.get_alias('Threshold-O' + str(i))
                    alias_out = DAN.get_alias('Trigger-I' + str(i))
                except IndexError:
                    print('End of finding alias')
                    break

        print(self.mappings, self.cb_id)

        # Recover Rules from database according to fetched alias.
        sa = self.cb_db.CB_SA[self.cb_id]
        rules = sa.rule_set
        for actuator_alias, (sensor_alias, order) in self.mappings.items():
            new_rule = rules.filter(lambda rule: rule.actuator_alias == actuator_alias and rule.sensor_alias == sensor_alias)[:]
            if not len(new_rule):
                new_rule = self.cb_db.UserRule(
                    **self.default_rule,
                    actuator_alias=actuator_alias,
                    sensor_alias=sensor_alias,
                    sa=sa
                )
                self.cb_db.commit()
        return

    @orm.db_session
    def check_rules(self):
        '''
        Rule checker for all rules set for this SA.
        Called by Subsystem every check period.

        Args:
            None

        Returns:
            None
        '''
        sa = self.cb_db.CB_SA[self.cb_id]
        for rule in sa.rule_set:
            print(rule)
            status = self.status[rule.sensor_alias]
            if rule.mode == 'on':
                if status['status'] != 'RED':
                    actuator_df = 'Trigger-I' + str(self.mappings[rule.actuator_alias][1])
                    DAN.push(actuator_df, 1)
            elif rule.mode == 'off':
                if status['status'] == 'RED':
                    actuator_df = 'Trigger-I' + str(self.mappings[rule.actuator_alias][1])
                    DAN.push(actuator_df, 0)
            # auto mode
            else:
                if rule.rule_type == 'sensor':
                    self.sensor_checker(
                        rule.rule_id, self.mappings[rule.actuator_alias]
                    )
                else:
                    self.timer_checker(
                        rule.rule_id, self.mappings[rule.actuator_alias]
                    )
            # check for sensor failure
            self.calibration_checker(
                rule.sensor_alias, rule.mode, status['status'], self.mappings[rule.actuator_alias], rule.rule_type, sa
            )
            if self.calibrate is True:
                print('Calibrating ', rule.sensor_alias)
            else:
                print('Not Calibrating ', rule.sensor_alias)
        return
    
    @orm.db_session
    def calibration_checker(self, sensor, mode, status, mapping, rule_type, sa):
        #outlier based
        if status == 'RED' and mode == 'auto' or mode == 'on':
            if sensor not in self.checking:
                sensor_df = 'Threshold-O' + str(mapping[1])
                data = DAN.pull(sensor_df)
                if data is not None:
                    # print('SAVE SENSOR DATA FOR CHECKING')
                    data = data[0]
                    self.checking[sensor] = datetime.datetime.now()
                    self.initial[sensor] = data
            else:
                if self.checking[sensor] == 0:
                    sensor_df = 'Threshold-O' + str(mapping[1])
                    data = DAN.pull(sensor_df)
                    if data is not None:
                        data = data[0]
                        self.checking[sensor] = datetime.datetime.now()
                        self.initial[sensor] = data
        
        if sensor in self.checking:
            if self.checking[sensor] != 0:
                time = datetime.datetime.now() - self.checking[sensor] 
                if time.total_seconds() > 15:
                    # print('SAVE DATA TO DATABASE')
                    sensor_df = 'Threshold-O' + str(mapping[1])
                    data = DAN.pull(sensor_df)
                    if data is not None:
                        data = data[0]
                        ascent = data-self.initial[sensor]
                        if self.calibrate == False:
                            self.cb_db.Outlier(
                                sensor = sensor, initial_data = self.initial[sensor], 
                                ascent = ascent, said = sa.cb_id
                            )
                            self.cb_db.commit()
                            self.outlier_test(sensor, self.initial[sensor], ascent)
                        self.checking[sensor] = 0
                    else:
                        pass
        
        # threshold based
        if rule_type == 'sensor' and mode == 'auto' and status == 'RED':
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
        elif rule_type == 'sensor' and mode == 'auto' and status == 'GREEN':
            if sensor in self.prev_status:
                if self.prev_status[sensor] == 1:
                    time_diff = datetime.datetime.now() - self.prev_time[sensor]
                    time_diff = time_diff.total_seconds()
                    self.prev_status[sensor] = 0
                    
                    if self.calibrate == False:
                        self.cb_db.Time_Threshold(
                            sensor = sensor, time_on = time_diff, said = sa.cb_id
                        )
                        self.cb_db.commit() 
                        self.threshold_test(sensor, time_diff)
        else:
            self.prev_status[sensor] = 0
        if self.calibrate is True:
            self.calib_complete_check(sensor)
        return
    
    def threshold_test(self, sensor, time_diff):
        # do the calculation with given data
        if sensor not in self.erlang:
            time_data = self.cb_db.Time_Threshold.select(lambda r: r.sensor == sensor and r.said == sa.cb_id)[:]
            actime = list()
            data_order = list()
            for data in time_data:
                data = data.to_dict()
                actime.append(data['time_on'])
                data_order.append(data['data_prio'])
            if(len(actime) < 50): pass
            else:  # delete the oldest time data 
                self.cb_db.Time_Threshold[min(data_order)].delete()
                self.cb_db.commit()
                pass
            histogram_bins = dict()
            find_medium = 0
            medium = -1
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
            for n in range(3,6):
                error = 0
                for lam in range(0, 10):
                    l = float(lam)/10
                    for bins in histogram_bins:
                        t = float(bins)*2+1
                        ft = ((l**n) * t**(n-1) * math.exp((-1)*l*t)) / math.factorial(n-1) 
                        error += abs(ft - histogram_bins[bins])
                    if least_error == 0: 
                        least_error = error
                        erlang[sensor] = (l, n)
                    elif least_error > error:
                        least_error = error
                        erlang[sensor] = (l, n)
            # found best lambda and n
            # erlang[sensor][0] = lambda   erlang[sensor][1] = n
            l = self.erlang[sensor][0]
            n = self.erlang[sensor][1]
            for t in range(int(medium), 60):
                pr = 0
                for i in range(1, n):
                    pr += (l**i * t**i * math.exp((-1)*l*t))/math.factorial(i)
                if pr <= 0.001:
                    threshold_time[sensor] = t
                    break
            if sensor not in threshold_time: threshold_time[sensor] = 60
        if sensor in threshold_time:
            if time_diff > threshold_time[sensor]: 
                self.calib_request(sensor)
                self.calibrate = True
        return 
    
    def outlier_test(self, sensor, initial_data, ascent):
        # do calculation for MSE here
        sensor_data = self.cb_db.Outlier.select(lambda r: r.sensor == sensor and r.said == sa.cb_id)[:]
        X = list()
        Y = list()
        order = list()
        for d in sensor_data:
            d = d.to_dict()
            order.append(d["data_prio"])
            X.append(d["initial_data"])
            Y.append(d["ascent"])
        if( len(X) > 10):
            x_avg = sum(X) / len(X)
            y_avg = sum(Y) / len(Y)
            x_mse = 0
            y_mse = 0
            xy_mse = 0
            for i in range(len(X)):
                x_mse += (X[i] - x_avg)**2
                y_mse += (Y[i] - y_avg)**2
                xy_mse += (X[i] - x_avg) * (Y[i] - y_avg)
            self.cb_db.Outlier[min(order)].delete()
            self.cb_db.commit()
            sample_size = len(X)
            # calculate the regression model and calculate m first
            m = xy_mse / x_mse
            b = y_avg - m * x_avg
            error = ascent - m * initial_data + b
            # for testing
            sigma_square = ( y_mse - m * xy_mse ) / (sample_size - 2)
            if(sigma_square < 0): sigma_square = (-1) * sigma_square
            sigma = math.sqrt ( sigma_square )

            rate_denom = ( 1 - 1/sample_size - (initial_data - x_avg)**2 / x_mse)
            if(rate_denom < 0): rate_denom = (-1) * rate_denom
            rate = ( error / sigma ) / math.sqrt( rate_denom )

            rate_change = (sample_size-3)/(sample_size-2-rate**2)
            if(rate_change < 0): rate_change = (-1) * rate_change
            rate = rate * math.sqrt(rate_change)
            
            if abs(rate) > 2: 
                self.calib_request(sensor) # error detected
                print('sensor in need of calibration')
                self.calibrate = True
            else:
                print('sensor normal')
                pass
        return
    
    def calib_request(self, sensor):
        # call this when the tests are not passed
        try:
            # DAN.calibrate(self.cb_db.CB_SA[self.cb_id].p_id)
            # temporary method
            cb = requests.Session()
            r = cb.post(
                f'http://{{config["iottalk_server"]}}:9999' + '/calibrate_sensor',
                json=('p_id': p_id,'sensor': sensor, 'state': None), 
                timeout=TIMEOUT
            )
            if r.status_code != 200: raise CSMError(r.text)
        except Exception as e:
            print("calibration request error: ")
            print(e)
        return
    
    def calib_complete_check(self, sensor):
        # under calibration mode, keep checking for DA's return message
        try:
            msg = DAN.pull('__Ctl_O__')
            if msg is not None:
                msg = msg[0][1]
                if len(msg) == 3:
                    if msg[2] is 'done':
                        # report to user calibration done
                        self.checking[sensor] = 0
                        self.calibrate = False
                        pass
                    elif msg[2] is 'failed':
                        # report to user calibration failed
                        self.checking[sensor] = 0
                        self.calibrate = False
                        pass
                    else:
                        pass
        except Exception as e:
            print("Pull control message error: ")
            print(e)
        return
    

    @orm.db_session
    def timer_checker(self, rule_id, mapping):
        """
        Timer-type rule checking handler. Push to IoTTalk server accordingly.

        Args:
            rule_id: The id of the rule to be checked.
            mapping: Tuple of format (sensor_alias, order of Device Feature).

        Returns:
            None
        """
        rule = self.cb_db.UserRule[rule_id]
        status = self.status[rule.sensor_alias]
        current = datetime.datetime.now()
        actuator_df = 'Trigger' + '-I' + str(mapping[1])
        time_open = datetime.datetime.combine(datetime.date.today(), rule.time_open)
        time_close = datetime.datetime.combine(datetime.date.today(), rule.time_close)
        exetime = rule.exetime

        if time_open > time_close:
            time_close = time_close + datetime.timedelta(days=1)

        satisfied = (current > time_open and current < time_close)
        about2trigger = (abs((time_open - current).total_seconds()) < 600 and time_open > current)
        expired = time.time() > (status['prev_trigger'] + rule.period)

        try:
            if not expired:
                if exetime == 0:  # timer set to not set
                    if status['status'] == 'RED':
                        DAN.push(actuator_df, 0)
                        status['status'] = 'GREEN'
                    elif status['status'] == 'YELLOW':
                        status['status'] = 'GREEN'
                else:
                    if status['status'] == 'RED':
                        if satisfied:
                            pass
                        else:
                            DAN.push(actuator_df, 0)
                            status['status'] = 'GREEN'
                    elif status['status'] == 'YELLOW':
                        if satisfied:
                            DAN.push(actuator_df, 1)
                            status['status'] = 'RED'
                            status['prev_trigger'] = time.time() + rule.exetime
                        elif about2trigger:
                            status['status'] = 'YELLOW'
                        else:
                            status['status'] = 'GREEN'
                    elif status['status'] == 'GREEN':
                        if satisfied:
                            DAN.push(actuator_df, 1)
                            status['status'] = 'RED'
                            status['prev_trigger'] = time.time() + rule.exetime
                        elif about2trigger:
                            status['status'] = 'YELLOW'
                        else:
                            status['status'] = 'GREEN'
            else:
                if status['status'] == 'RED':
                    DAN.push(actuator_df, 0)
                    status['status'] = 'GREEN'
                else:
                    status['status'] = 'GREEN'
        except Exception as err:
            print(err)
        self.socket.send_json(status)
        return

    @orm.db_session
    def sensor_checker(self, rule_id, mapping):
        """
        Sensor-type rule checking handler. Push to IoTTalk server accordingly.

        Args:
            rule_id: The id of the rule to be checked.
            mapping: Tuple of format (sensor_alias, order of Device Feature).

        Returns:
            None
        """
        sensor_df = 'Threshold-O' + str(mapping[1])
        data = DAN.pull(sensor_df)
        if data is None:
            return

        data = data[0]
        rule = self.cb_db.UserRule[rule_id]
        status = self.status[rule.sensor_alias]
        status['value'] = data
        self.df_hist_val[rule.sensor_alias].append(data)
        actuator_df = 'Trigger-I' + str(mapping[1])

        try:
            avg = sum(self.df_hist_val[rule.sensor_alias]) / len(self.df_hist_val[rule.sensor_alias])
            if 'notset' in rule.comparison_open and 'notset' in rule.comparison_close:
                if status['status'] == 'RED':
                    DAN.push(actuator_df, 0)
                status['status'] = 'GREEN'
                return
            elif 'notset' in rule.comparison_open:
                action = 'CLOSE'
                satisfied, next_action = self.condition_handler[rule.comparison_close](data, rule.threshold_close, avg)
            elif 'notset' in rule.comparison_close:
                action = 'OPEN'
                satisfied, next_action = self.condition_handler[rule.comparison_open](data, rule.threshold_open, avg)
            else:
                satisfied, next_action = self.condition_handler[rule.comparison_open](data, rule.threshold_open, avg)
                action = 'OPEN'
                if not satisfied:
                    action = 'CLOSE'
                    satisfied, next_action = self.condition_handler[rule.comparison_close](data, rule.threshold_close, avg)

            expired = time.time() > (status.prev_trigger + rule.period)
            if not expired:
                if status['status'] == 'RED':
                    if action == 'CLOSE':
                        if satisfied:
                            DAN.push(actuator_df, 0)
                            if next_action == 'YELLOW':
                                status['status'] = 'YELLOW'
                            else:
                                status['status'] = 'GREEN'
                elif status['status'] == 'GREEN':
                    if action == 'OPEN':
                        if satisfied:
                            DAN.push(actuator_df, 1)
                            status['status'] = 'RED'
                            status.prev_triiger = time.time() + rule.exetime
                        else:
                            if next_action == 'YELLOW':
                                status['status'] = 'YELLOW'
                else:
                    if action == 'OPEN':
                        if satisfied:
                            DAN.push(actuator_df, 1)
                            status['status'] = 'RED'
                            status['prev_trigger'] = time.time() + rule.exetime
                        else:
                            if next_action != 'YELLOW':
                                status['status'] = 'GREEN'
                    else:
                        if next_action != 'YELLOW':
                            status['status'] = 'GREEN'
            else:
                if status['status'] == 'RED':
                    DAN.push(actuator_df, 0)
                    status['status'] = 'GREEN'
                else:
                    status['status'] = 'GREEN'

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
            satisfied: whether the rule is satisfied by arg data
            status: Card status in UI.
        """
        if data > threshold:
            satisfied = True
            status = 'RED'
        else:
            satisfied = False
            print('bigger', 0.5 * (threshold - avg) + avg)
            if data > 0.5 * (threshold - avg) + avg:
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


sa = AG_SA('{cb_id}', {config}, '{mac_addr}')

sa.connect_db()
sa.recover()


while True:
    print('start checking rules')
    sa.check_rules()
    time.sleep(5)
