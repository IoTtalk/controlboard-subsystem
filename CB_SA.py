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

    def recover(self):
        '''
        Recover SA CBElements & generate Rule status.

        Args: None.

        Returns: None
        '''
        self.status = dict()
        print("print sa's rules")
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
            print("self.rules.items() : ",self.rules.items())
            for df_order, rule in self.rules.items():
                status = self.status[rule["rule_id"]]
                print("\n\nAAA status : ",status,"\n\n")
                print("\n\nBBB rule : ",rule,"\n\n")
                actuator_df = "CBElement-TI" + str(df_order)
                sensor_df = "CBElement-O" + str(df_order)
                data = DAN.pull(sensor_df)
                print("\n???????? : ",data,"\n")
                if data is None:
                    print("No sensor data pulled")
                else:
                    candidate_sensors = rule["sensor_alias"].split(",")
                    if len(candidate_sensors) == 1:
                        data = data[0]
                    else:
                        data = data[0][self.rules[df_order]["sensor_index"]]
                    if data <= -10000:
                        data += 10001
                        print("in !!!! \n", data)
                        print(status["status"])
                        status["status"] = "RED" if data else "GREEN"
                        print("bbb : ",status)
                        continue
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
                print("temp rule : ", temp_rule)
                DAN.push(actuator_df, temp_rule)

                status["value"] = data if data is not None else status["value"]
                print("CCC status", status)
                self.socket.send_json(status)
        except Exception as err:
            print("Checking CBElement failed, ", err)
        return


sa = AG_SA('{sa_id}', {config}, '{mac_addr}', '{sa_name}', {rules})
sa.recover()
DAN.state = "RESUME"

while True:
    print('start checking rules of', sa.sa_id)
    sa.check_rules()
    time.sleep(5)
