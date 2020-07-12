import time
import uuid
import datetime
import atexit

from pony import orm

from utils import running_sa


import DAN


class AG_SA():       
    def __init__(self, cb_id, config, mac_addr):
        '''
        Initialization of a CB_SA

        Args:
            cb_id: ID of this CB_SA from Database.
            mappings: Mapping of actuator to sensors.
            config: Infomation for connecting to Subsystem, should contain IP, port, username, password.

        Instance variables:
            rules: User-defined rules in dictionary to avoid huge querying rules resulting from checking rule satisfaction.
            {{
                actuator_alias1:
                {{
                    "rule_type": "timer" or "sensor", required.
                    "actuator_alias": string, required.
                    "sensor_alias": string, required if Type is "sensor".
                    "threshold_close": integer, required if Type is "sensor".
                    "threshold_open": integer, required if Type is "sensor".
                    "comparison_close": string, required.
                    "comparison_open": string, required.
                    "time_open": datetime string, required if Type is "timer".
                    "time_close": datetime string, required if Type is "timer".
                    "trigger": whether this actuator is triggered or not.
                    "status": the color(green/yellow/red) this rule should present.
                }}
            }}
            mappings: A dictionary of the following format.
            {{
                'actuator_alias1': (sensor_alias1, DF order on IoTTalk GUI)
            }}
            cb_id: ID for this SA, used in Database querying.
            df_hist_val: History values of sensors manipulated by this SA.
            df_hist_len: # recorded history values.
            config: Database config containing the following information.
                host: IP address of the database.
                port: Port of the database.
                user: Account provided to connect the database.
                pwd: Password provided to connect the database.
                dbname: Which Database to use.
            cb_db: Database session for this SA.
            mac_addr: Mac address of this SA.

        Returns:
            None
        '''
        self.rules = dict()
        self.mappings = dict()
        self.df_hist_val = dict()
        self.df_hist_len = dict()
        self.cb_id = cb_id
        self.config = config
        self.cb_db = orm.Database()
        if mac_addr is not 'None':
            self.mac_addr = mac_addr
        else:
            self.mac_addr = str(uuid.uuid4())
        
        condition_handler = {
            'bigger': self.bigger,
            'smaller': self.smaller,
            'biggerandequal': self.bigger_equal,
            'smallerandequal': self.smaller_equal
        }

        ctlboard_profile = {
            'd_name': str(cb_id) + 'Controlboard',
            'dm_name': 'ControlBoard',
            'u_name': 'yb',
            'is_sim': False,
            'df_list': ['Threshold-O1', 'Trigger-I1', 'Threshold-O2', 'Trigger-I2',
                        'Threshold-O3', 'Trigger-I3', 'Threshold-O4', 'Trigger-I4',
                        'Threshold-O5', 'Trigger-I5']
        }

        DAN.profile = ctlboard_profile
        #DAN.device_registration_with_retry(f"http://{{config['iottalk_server']}}:9999", self.mac_addr)

        class UserRule(self.cb_db.Entity):
            rule_id = orm.PrimaryKey(int, auto=True)  # For AG_SA to write status.
            rule_type = orm.Required(str)  # Sensor / Timer.
            actuator_alias = orm.Required(str)  # Alias of the actuator in this rule.
            sensor_alias = orm.Optional(str)  # Alias of the actuator in this rule, required if rule_type is 'sensor'.
            threshold_open = orm.Optional(float)  # Sensor value to decide trigger actuator or not.
            threshold_close = orm.Optional(float)  # Sensor value to decide close actuator or not.
            comparison_open = orm.Optional(str)  # Comparison method to decide trigger actuator or not.
            comparison_close = orm.Optional(str)  # Comparison method to decide close actuator or not.
            time_open = orm.Optional(datetime.time)  # Trigger actuator every when current time exceeds time_open.
            time_close = orm.Optional(datetime.time)  # Close actuator every when current time exceeds time_open.
            exetime = orm.Optional(int)  # execution time for periodically execution
            mode = orm.Required(str)
            sa = orm.Required("CB_SA")  # which SA it belongs to

        class CB_SA(self.cb_db.Entity):
            cb_id = orm.PrimaryKey(int, auto=True)  # id of this SA.
            cb_name = orm.Required(str)  # User-defined cb_name. Can be repeated.
            rule_set = orm.Set("UserRule")
            account_set = orm.Set("CB_Account")  # accounts that can access this SA.


        class CB_Account(self.cb_db.Entity):
            account = orm.Required(str)  # Account of this user.
            privilige = orm.Required(int)  # User level of this user.
            sa_set = orm.Set("CB_SA")  # SAs this user can see.


        class CB_Status(self.cb_db.Entity):
            rule_id = orm.Required(int)  # For Subsystem to findout which rule this status entry represent.
            status = orm.Required(str)  # The status of the corresponding rule, should be 'red'/'yellow'/'green'.
            value = orm.Required(float)  # The sensory value received from IoTtalk.


    def connect_db(self):
        '''
        Connect to correspoinding database

        Args:
            config: Database config containing
                host: IP address of the database.
                port: Port of the database.
                user: Account provided to connect the database.
                pwd: Password provided to connect the database.
                dbname: Which Database to use.

        Returns:
            subsystem_db: connected db session of the database.
        '''
        retry_times = 0
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

    @orm.db_session()
    def recover(self):
        '''
        Recover SA UserRules from Database & 
        generate mappings of (actuator, sensor) of IoTTalk GUI.

        Args: None.

        Returns: True or False
            True: Recover succeeded.
            False: Recover failed. 
        '''

        """
        while DAN.state != 'RESUME':
            print('Bind first')
            time.sleep(1)
        
        alias_in = DAN.get_alias('Threshold-O' + str(1))
        alias_out = DAN.get_alias('Trigger-I' + str(1))

        print(alias_in, alias_out)
        print(self.mac_addr)
        i = 1
        while len(alias_in):
            try:
                if 'Threshold' not in alias_in[0] and 'Trigger' not in alias_out[0]:
                    self.mappings[alias_out[0]] = (alias_in[0], i)

                i += 1
                alias_in = DAN.get_alias('Threshold-O' + str(i))
                alias_out = DAN.get_alias('Trigger-I' + str(i))
            except IndexError as err:
                print('End of finding alias')
        """
        self.mappings["changed"] = ("sensor", 1)
        self.mappings["FAN"] = ("tests", 2)
        with orm.db_session():
            sa = self.cb_db.CB_SA[self.cb_id]
            rules = sa.rule_set
        for rule in rules:
            tmp = rule.to_dict()
            self.rules[tmp['actuator_alias']] = tmp      


        return 


    def terminate(self):
        '''
        Termination of this CB SA.

        Args:
            None.

        Returns:
            Boolean indicating termination succeed or failed.
        '''
        return

    def check_rules(self):
        '''
        Rule checker for all rules set for this SA.
        Called by Subsystem every check period.

        Args:
            None

        Returns:
            None
        # '''
        # for rule in self.rules:
        #     if rule.rule_type == "timer":
        #         CB_SA.time_checker(self.da, self.logger, rule)
        #     else:
        #         CB_SA.sensor_handler(self.da, self.logger, rule)
        data = DAN.pull('Threshold-O1')

        print('Pulled from AG:', data)

        DAN.push('Trigger-I1', 1)

        return

    def sensor_checker(cls, comparison, threshold, data, action, actuator_alias, sensor_alias):
        """
        Sensor-type rule checking worker.

        Args:
            cls: The SA that calls this method
            comparison: the comparison type. Represented as a String like 'bigger', 'smaller'...
            threshold: threshold settings from rule_info in memory.
            data: data pulled from IoTTalk server.
            action: 'open' or 'close' indicating what needs to be done if rule satisfied.
            actuator_alias: alias of actuator, stored in memory.
            sensor_alias: alias of sensor, stored in memory.

        Returns:
            to_trigger: The action needs to be done by Sensor-type handler.
                'OPEN': Open the actuator by pushing 1 to IoTTalk Server
                'CLOSE': Close the actuator by pushing 1 to IoTTalk Server
                'STAY': Do nothing

        """
        avg = sum(list(cls.df_hist_val[sensor_alias])) / len(cls.df_hist_val[sensor_alias])
        print('current avg:', avg)
        triggered, color = condition_handler[comparison](float(data), float(threshold), avg)
        to_trigger = 'STAY'
        print('Satisfied?', triggered)
        if triggered:
            if action == 'open':
                to_trigger = 'OPEN'
                utils.rule_info[actuator_alias]['status'] = 'red'
            else:
                to_trigger = 'CLOSE'
                utils.rule_info[actuator_alias]['status'] = 'green'
        if color == 'yellow':
            utils.rule_info[actuator_alias]['status'] = color

        return to_trigger

    def time_checker(da, actuator_alias, sensor_alias, order):
        """
        Timer-type rule checking handler. Push to IoTTalk server accordingly

        Args:
            actuator_alias: alias of actuator, stored in memory.
            sensor_alias: alias of sensor, stored in memory.
            order: which pair of (actuator, sensor) mappings is being checked.

        Returns:
            None
        """
        current = datetime.datetime.now()
        actuator_name = 'Trigger' + '-I' + str(order + 1)
        time_open = datetime.datetime.combine(datetime.date.today(), utils.rule_info[actuator_alias]['time_open'])
        time_close = datetime.datetime.combine(datetime.date.today(), utils.rule_info[actuator_alias]['time_close'])
        exetime = utils.rule_info[actuator_alias]['exetime']

        if time_open > time_close:
            time_close = time_close + datetime.timedelta(days=1)

        if exetime == 0:  # timer set to not set
            if utils.rule_info[actuator_alias]['trigger'] is True:
                da.push(actuator_name, 0)
                utils.rule_info[actuator_alias]['trigger'] = False
        else:
            if current > time_open and current < time_close:
                if utils.rule_info[actuator_alias]['trigger'] is False:
                    utils.rule_info[actuator_alias]['trigger'] = True
                    self.da.push(actuator_name, 1)
                utils.rule_info[actuator_alias]['status'] = 'red'
            else:
                if utils.rule_info[actuator_alias]['trigger'] is True:
                    utils.rule_info[actuator_alias]['trigger'] = False
                    self.da.push(actuator_name, 0)
                if abs((time_open - current).total_seconds()) < 600 and time_open > current:
                    utils.rule_info[actuator_alias]['status'] = 'yellow'
                else:
                    utils.rule_info[actuator_alias]['status'] = 'green'

        return

    def sensor_handler(da, actuator_alias, sensor_alias, order):
        """
        Sensor-type rule checking handler. Push to IoTTalk server accordingly.

        Args:
            actuator_alias: alias of actuator, stored in memory.
            sensor_alias: alias of sensor, stored in memory.
            order: which pair of (actuator, sensor) mappings is being checked.

        Returns:
            None
        """
        actuator_name = 'Trigger' + '-I' + str(order + 1)

        # -------------Comparison with threshold--------------
        comparison_open = utils.rule_info[actuator_alias]['comparison_open']
        comparison_close = utils.rule_info[actuator_alias]['comparison_close']

        if comparison_open != 'notset':
            threshold_open = utils.rule_info[actuator_alias]['threshold_open']
        if comparison_close != 'notset':
            threshold_close = utils.rule_info[actuator_alias]['threshold_close']
        if sensor_alias not in utils.df_hist_val:
            self.logger.info("No data pulled from IoTTalk, skip checking")
            return
        else:
            data = utils.df_hist_val[sensor_alias][-1]
        # filter notset
        try:
            if 'notset' in comparison_open and 'notset' in comparison_close:
                utils.rule_info[actuator_alias]['trigger'] = False
                utils.rule_info[actuator_alias]['status'] = 'red'
                # self.logger.info(f'Change all comparison to notset, close actuator {{actuator_alias}} and corresponding pushing thread')
                utils.pushing_thread_dict[actuator_alias][1] = False
                utils.pushing_thread_dict.pop(actuator_alias, None)
                to_trigger = 'NOTSET'

            elif 'notset' in comparison_open and 'notset' not in comparison_close:
                to_trigger = self.sensor_checker(comparison_close, threshold_close, data, 'close', actuator_alias, sensor_alias)

            elif 'notset' not in comparison_open and 'notset' in comparison_close:
                to_trigger = self.sensor_checker(comparison_open, threshold_open, data, 'open', actuator_alias, sensor_alias)

            else:
                to_trigger = self.sensor_checker(comparison_open, threshold_open, data, 'open', actuator_alias, sensor_alias)
                if to_trigger == 'STAY':
                    to_trigger = self.sensor_checker(comparison_close, threshold_close, data, 'close', actuator_alias, sensor_alias)

            if to_trigger == 'CLOSE':
                if utils.rule_info[actuator_alias]['trigger'] is True:
                    self.da.push(actuator_name, 0)
                # self.logger.info(f'sensor {{sensor_alias}} close {{actuator_alias}}, comparison: {{comparison_close}}, 
                # threshold: {{threshold_close}}, data pulled: {{data}}')
                utils.rule_info[actuator_alias]['trigger'] = False

            elif to_trigger == 'OPEN':
                if utils.rule_info[actuator_alias]['trigger'] is False:
                    self.da.push(actuator_name, 1)
                # self.logger.info(f'sensor {{sensor_alias}} trigger {{actuator_alias}}, comparison: {{comparison_open}}, threshold: {{threshold_open}}, data pulled: {{data}}')
                utils.rule_info[actuator_alias]['trigger'] = True

            print(utils.rule_info[actuator_alias]['trigger'], actuator_alias)
        except Exception as ep:
            self.logger.error(ep)

        return
    
    def bigger(data, threshold, avg):
        """
        Check if data > threshold. Return comparison results as boolean, string.

        Args:
            data: data pulled from IoTTalk server.
            threshold: threshold settings from rule_info in memory.
            avg: the average of history data stored in memory.

        Returns:
            triggered: whether the rule is satisfied by arg data
            color: Card color in UI.
        """
        if data > threshold:
            triggered = True
            color = 'green'
        else:
            triggered = False
            print('bigger', 0.5 * (threshold - avg) + avg)
            if data > 0.5 * (threshold - avg) + avg:
                color = 'yellow'
            else:
                color = 'unchanged'

        return triggered, color

    def smaller(data, threshold, avg):
        """Check if data < threshold. Return comparison results as boolean, string.

        Args:
            data: data pulled from IoTTalk server.
            threshold: threshold settings from rule_info in memory.
            avg: the average of history data stored in memory.

        Returns:
            triggered: whether the rule is satisfied by arg data
            color: Card color in UI.
        """
        if data < threshold:
            triggered = True
            color = 'green'
        else:
            triggered = False
            print('smaller', 0.22 * (avg - threshold) + threshold)
            if data < 0.22 * (avg - threshold) + threshold:
                print(data, 'yellow')
                color = 'yellow'
            else:
                color = 'unchanged'
        return triggered, color

    def bigger_equal(data, threshold, avg):
        """Check if data >= threshold. Return comparison results as boolean, string.

        Args:
            data: data pulled from IoTTalk server.
            threshold: threshold settings from rule_info in memory.
            avg: the average of history data stored in memory.

        Returns:
            triggered: whether the rule is satisfied by arg data
            color: Card color in UI.
        """
        if data >= threshold:
            triggered = True
            color = 'green'
        else:
            print('biggerequal', 0.78 * (threshold - avg) + avg)
            triggered = False
            if data > 0.78 * (threshold - avg) + avg:
                color = 'yellow'
            else:
                color = 'unchanged'

        return triggered, color

    def smaller_equal(data, threshold, avg):
        """Check if data <= threshold. Return comparison results as boolean, string.

        Args:
            data: data pulled from IoTTalk server.
            threshold: threshold settings from rule_info in memory.
            avg: the average of history data stored in memory.

        Returns:
            triggered: whether the rule is satisfied by arg data
            color: Card color in UI.
        """
        if data <= threshold:
            triggered = True
            color = 'green'
        else:
            triggered = False
            print('smallerequal', 0.22 * (avg - threshold) + threshold)
            if data < 0.22 * (avg - threshold) + threshold:
                color = 'yellow'
            else:
                color = 'unchanged'
        return triggered, color

config = {
    "host": '127.0.0.1',
    'port': 3306,
    'user': 'cbsubsystem',
    'pwd': 'pcs54784',
    'dbname': 'controlboard'
}

#sa = AG_SA('{account}', config, '{mac_addr}')

# for testing
sa = AG_SA(1, config, '{mac_addr}')
running_sa['1'] = sa


sa.connect_db()
sa.recover()

#atexit.register(sa.terminate)

#while True:
#    sa.check_rules()
#    time.sleep(5)
