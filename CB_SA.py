import time
import uuid
import datetime


import zmq


import DAN


class AG_SA():
    def __init__(self, sa_id, config, mac_addr, sa_name, rules):
        '''
        Initialization of a CB_SA

        Args:
            sa_id: ID of this CB_SA from Database.
            sa_name: Name of this CB_SA.
            mac_addr: Mac address of this SA.
            config: Infomation for connecting to Subsystem.
            rules: UserRules of this SA.

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
        self.times = 0
        if mac_addr != 'None':
            self.mac_addr = mac_addr
        else:
            self.mac_addr = str(uuid.uuid4())

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
            "df_list": ["CBElement-O1", "CBElement-TI1", "CBElement-O2", "CBElement-TI2",
                        "CBElement-O3", "CBElement-TI3", "CBElement-O4", "CBElement-TI4",
                        "CBElement-O5", "CBElement-TI5"]
        }}
        context = zmq.Context()
        self.socket = context.socket(zmq.PUB)
        self.socket.connect(f"tcp://{{config['host_zmq']}}:{{config['port_zmq']}}")
        self.socket.send(b"hello world")

        DAN.profile = ctlboard_profile
        DAN.device_registration_with_retry(f'http://{{config["iottalk_server"]}}:9999', self.mac_addr)

    def recover(self):
        '''
        Recover SA UserRules & generate Rule status.

        Args: None.

        Returns: None
        '''
        self.status = dict()
        print("print sa's rules")
        DAN.state = "RESUME"
        for (df_order, rule) in self.rules.items():
            rule_id = rule["rule_id"]
            self.status[rule_id] = {{
                "prev_trigger": -10000,  # An apparently impossible number.
                "status": "GREEN",  # RED / YELLOW / GREEN
                "value": 0,  # Current value of the selected sensor.
                "rule_id": rule_id  # rule_id of this status recorder.
            }}
        print("recovered rules:", self.rules)
        print("status recorder: ", self.status)
        return

    def check_rules(self):
        '''
        Rule checker for all rules of this SA.
        Iteratively executed to generate status and open / close actuators.

        Args: None

        Returns: None
        '''
        try:
            for df_order, rule in self.rules.items():
                status = self.status[rule["rule_id"]]
                actuator_df = "CBElement-TI" + str(df_order)
                sensor_df = "CBElement-O" + str(df_order)
                data = DAN.pull(sensor_df)
                if data is None:
                    print("No sensor data pulled")
                else:
                    candidate_sensors = rule["sensor_alias"].split(",")
                    if len(candidate_sensors) == 1:
                        data = data[0]
                    else:
                        data = data[0][self.rules[df_order]["sensor_index"]]
                if self.times < 5:
                    temp_rule = {{
                        "threshold_open": rule["threshold_open"],
                        "threshold_close": rule["threshold_close"],
                        "comparison_open": rule["comparison_open"],
                        "comparison_close": rule["comparison_close"],
                        "time_open": [rule["time_open"].hour, rule["time_open"].minute, rule["time_open"].second],
                        "time_close": [rule["time_close"].hour, rule["time_close"].minute, rule["time_close"].second],
                        "mode": rule["mode"],
                        "weekday": rule["weekday"],
                        "duty_pos": rule["duty_pos"],
                        "duty_neg": rule["duty_neg"],
                        "sensor_val": data
                    }}
                    DAN.push(actuator_df, temp_rule)
                else:
                    DAN.push(actuator_df, {{"sensor_val": data}})
                status["value"] = data if data is not None else status["value"]
                if rule["mode"] == "ON":
                    if status["status"] != "RED":
                        status["status"] = "RED"
                elif rule["mode"] == "OFF":
                    if status["status"] == "RED":
                        status["status"] = "GREEN"
                # auto mode
                else:
                    weekdays = [int(x) for x in rule["weekday"].split(",")] \
                        if len(rule["weekday"]) else list()
                    if len(weekdays) == 0 or (datetime.datetime.today().weekday() in weekdays) or 7 in weekdays:
                        if rule["mode"] == "Sensor" and data is not None:
                            self.sensor_checker(df_order, data)
                        elif rule["mode"] == "Timer":
                            self.timer_checker(df_order)
                    else:
                        if status["status"] == "RED":
                            status["status"] = "GREEN"
                self.socket.send_json(status)
            if (self.times < 5):
                self.times += 1
        except Exception as err:
            print("Checking UserRule failed, ", err)
        return

    def time_check_worker(self, df_order):
        """
        Work function for timing check, added for sensor-type's timing checking feature

        Args:
            df_order: The IDF/ODF pair of ControlBoard to pull/push data.

        Returns:
            satisfied: Boolean, whether timing correct.
        """
        rule = self.rules[df_order]
        current = datetime.datetime.now()
        time_open = datetime.datetime.combine(datetime.date.today(), rule["time_open"])
        time_close = datetime.datetime.combine(datetime.date.today(), rule["time_close"])
        if time_open > time_close:
            time_close = time_close + datetime.timedelta(days=1)
        return (current > time_open and current < time_close)

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
                        status["status"] = "GREEN"
                elif status["status"] == "YELLOW":
                    if satisfied:
                        status["status"] = "RED"
                        status["prev_trigger"] = current_epoch
                    elif about2trigger:
                        status["status"] = "YELLOW"
                    else:
                        status["status"] = "GREEN"
                elif status["status"] == "GREEN":
                    if satisfied:
                        status["status"] = "RED"
                        status["prev_trigger"] = current_epoch
                    elif about2trigger:
                        status["status"] = "YELLOW"
                    else:
                        status["status"] = "GREEN"
            else:
                status["status"] = "GREEN"
        except Exception as err:
            print("Check Timer UserRule failed", err)
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
        try:
            avg = sum(self.df_hist_val[sensor_alias]) / len(self.df_hist_val[sensor_alias])
            if "notset" in rule["comparison_open"] and "notset" in rule["comparison_close"]:
                status["status"] = "GREEN"
                return
            elif not self.time_check_worker(df_order):
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
                            if next_action == "YELLOW":
                                status["status"] = "YELLOW"
                            else:
                                status["status"] = "GREEN"
                elif status["status"] == "GREEN":
                    if action == "OPEN":
                        if satisfied:
                            status["status"] = "RED"
                            status["prev_trigger"] = current
                        else:
                            if next_action == "YELLOW":
                                status["status"] = "YELLOW"
                else:
                    if action == "OPEN":
                        if satisfied:
                            status["status"] = "RED"
                            status["prev_trigger"] = current
                        else:
                            if next_action != "YELLOW":
                                status["status"] = "GREEN"
                    else:
                        if next_action != "YELLOW":
                            status["status"] = "GREEN"
            else:
                status["status"] = "GREEN"
            return
        except Exception as err:
            print("check Sensor UserRule failed", err)

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


sa = AG_SA('{sa_id}', {config}, '{mac_addr}', '{sa_name}', {rules})
sa.recover()


while True:
    print('start checking rules of', sa.sa_id)
    sa.check_rules()
    time.sleep(5)
