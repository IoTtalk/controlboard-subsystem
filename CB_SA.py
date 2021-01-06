import time
import uuid
import datetime


# from collections import deque


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

        Returns:
            None
        '''
        self.df_hist_val = dict()
        self.sa_id = int(sa_id)
        self.config = config
        self.cb_db = orm.Database()
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
        print(f"tcp://{{config['host_zmq']}}:{{config['port_zmq']}}")
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
        DAN.state = "RESUME"
        self.status = dict()
        self.rules = dict()
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
            if rule["mode"] == "ON":
                if status["status"] != "RED":
                    DAN.push(actuator_df, 1)
            elif rule["mode"] == "OFF":
                if status["status"] == "RED":
                    DAN.push(actuator_df, 0)
            # auto mode
            else:
                weekdays = rule["weekday"].split(",") if len(rule["weekday"]) else list()
                if len(weekdays) == 0 or (datetime.datetime.today().weekday() in weekdays) or 7 in weekdays:
                    if rule["mode"] == "Sensor":
                        self.sensor_checker(df_order)
                    else:
                        self.timer_checker(df_order)
            self.socket.send_json(status)

        return

    def timer_checker(self, df_order):
        """
        Timer-type rule checking handler. Push to IoTTalk server accordingly.

        Args:
            df_order: The IDF/ODF pair of ControlBoard to pull/push data.

        Returns:
            None
        """
        rule = self.cb_db.UserRule[rule_id]
        status = self.status[rule.sensor_alias]
        current = datetime.datetime.now()
        actuator_df = 'Trigger' + '-I' + str(mapping[1])
        time_open = datetime.datetime.combine(datetime.date.today(), rule.time_open)
        time_close = datetime.datetime.combine(datetime.date.today(), rule.time_close)
        duty_neg = rule.duty_neg

        if time_open > time_close:
            time_close = time_close + datetime.timedelta(days=1)

        satisfied = (current > time_open and current < time_close)
        about2trigger = (abs((time_open - current).total_seconds()) < 600 and time_open > current)
        expired = time.time() > (status['prev_trigger'] + rule.duty_pos)

        try:
            if not expired:
                if duty_neg == 0:  # timer set to not set
                    if status['status'] == 'RED':
                        DAN.push(actuator_df, 0)
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
                            status['prev_trigger'] = time.time() + rule.duty_neg
                        elif about2trigger:
                            status['status'] = 'YELLOW'
                        else:
                            status['status'] = 'GREEN'
                    elif status['status'] == 'GREEN':
                        if satisfied:
                            DAN.push(actuator_df, 1)
                            status['status'] = 'RED'
                            status['prev_trigger'] = time.time() + rule.duty_neg
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
        return

    def sensor_checker(self, df_order):
        """
        Sensor-type rule checking handler. Push to IoTTalk server accordingly.

        Args:
            df_order: The IDF/ODF pair of ControlBoard to pull/push data.

        Returns:
            None
        """
        sensor_df = "Threshold-O" + str(df_order)
        rule = self.rules[df_order]
        data = DAN.pull(sensor_df)
        if data is None:
            print("No sensor data pulled")
            return
        candidate_sensors = rule["sensor_alias"].split(",")
        if len(candidate_sensors) == 1:
            data = data[0]
        else:
            data = data[0][self.rules[df_order]["sensor_index"]]
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
                print(1)
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

            expired = (rule["duty_pos"] != 0) and (status["prev_trigger"] != -10000) \
                and (time.time() < (status["prev_trigger"] + rule["duty_pos"]))
            print(satisfied, next_action, expired)
            if not expired:
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
                            status["prev_trigger"] = time.time() + rule["duty_neg"]
                        else:
                            if next_action == "YELLOW":
                                status["status"] = "YELLOW"
                else:
                    if action == "OPEN":
                        if satisfied:
                            DAN.push(actuator_df, 1)
                            status["status"] = "RED"
                            status["prev_trigger"] = time.time() + rule["duty_neg"]
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
                else:
                    status["status"] = "GREEN"
            print(status)
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


sa = AG_SA('{sa_id}', {config}, '{mac_addr}', '{sa_name}')

sa.connect_db()
sa.recover()


while True:
    print('start checking rules')
    sa.check_rules()
    time.sleep(10)
