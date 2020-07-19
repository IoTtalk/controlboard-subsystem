import time
import uuid
import datetime
import atexit


from pony import orm


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
            rules: User-defined rules to avoid redundant querying rules resulting from checking rule satisfaction.
            [
                (rule entity, status entity)
            ]
            mappings: A dictionary of the following format.
            {
                'actuator_alias1': (sensor_alias1, DF order on IoTTalk GUI)
            }
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
            default_rule: basic default rule settings.

        Returns:
            None
        '''
        self.rules = list()
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


        DAN.profile = ctlboard_profile
        DAN.device_registration_with_retry(f"http://{{config['iottalk_server']}}:9999", self.mac_addr)

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
            period = Required(int)  # Period functionality.
            mode = orm.Required(str)
            sa = orm.Required("CB_SA")  # which SA it belongs to

        class CB_SA(cb_db.Entity):
            cb_id = PrimaryKey(int, auto=True)  # id of this SA.
            cb_name = Required(str)  # User-defined cb_name. Can be repeated.
            ag_token = Required(LongStr) # AG-returned token
            mac_addr = Required(LongStr) # Mac-addr of this SA
            rule_set = Set(UserRule)
            account_set = Set("CB_Account")  # accounts that can access this SA.


        class CB_Account(self.cb_db.Entity):
            account = orm.Required(str)  # Account of this user.
            privilige = orm.Required(int)  # User level of this user.
            sa_set = orm.Set("CB_SA")  # SAs this user can see.


        class CB_Status(self.cb_db.Entity):
            rule_id = orm.PrimaryKey(int)  # For Subsystem to findout which rule this status entry represent.
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
        # Pulling Alias
        DAN.state = "RESUME"
        while len(self.mappings) == 0:        
            alias_in = DAN.get_alias('Threshold-O' + str(1))
            alias_out = DAN.get_alias('Trigger-I' + str(1))
            print('Please bind first')

            i = 1
            while len(alias_in):
                try:
                    if 'Threshold' not in alias_in[0] and 'Trigger' not in alias_out[0]:
                        self.mappings[alias_out[0][:-3]] = (alias_in[0][:-3], i)
                    i += 1
                    alias_in = DAN.get_alias('Threshold-O' + str(i))
                    alias_out = DAN.get_alias('Trigger-I' + str(i))
                except IndexError as err:
                    print('End of finding alias')
                    break

            time.sleep(2)
        print(self.mappings, self.cb_id)

        # Recover Rules from database according to fetched alias.
        sa = self.cb_db.CB_SA[self.cb_id]
        rules = sa.rule_set
        for actuator_alias, (sensor_alias, order) in self.mappings.items():
            new_rule = rules.filter(lambda rule: rule.actuator_alias==actuator_alias and rule.sensor_alias==sensor_alias)[:]
            if not len(new_rule):
                new_rule = self.cb_db.UserRule(
                    **self.default_rule,
                    actuator_alias=actuator_alias,
                    sensor_alias=sensor_alias,
                    sa = sa
                )

                new_status = self.cb_db.CB_Status(
                    rule_id=new_rule.rule_id,
                    status='GREEN',
                    value=0
                )

                self.cb_db.commit()
                self.rules.append((new_rule, new_status))
            else:
                self.rules.append((new_rule[0], CB_Status[new_rule[0].rule_id]))

        print(self.rules)

        return 

    def check_rules(self):
        '''
        Rule checker for all rules set for this SA.
        Called by Subsystem every check period.

        Args:
            None

        Returns:
            None
        '''
        for rule, status in self.rules:
            if rule.mode == 'on':
                if status.status != 'RED':
                    actuator_df = 'Trigger-I' + str(self.mappings[rule.actuator_alias])
                    DAN.push(actuator_df, 1)
            elif rule.mode == 'off':
                if status.status == 'RED':
                    actuator_df = 'Trigger-I' + str(self.mappings[rule.actuator_alias])
                    DAN.push(actuator_df, 0)

            # auto mode
            if rule.rule_type == 'sensor':
                sensor_checker(
                    rule, status, self.mappings[rule.actuator_alias]
                )
            else:
                timer_checker(
                    rule, status, self.mappings[rule.actuator_alias]
                )

        return

    @staticmethod
    def timer_checker(actuator_alias, sensor_alias, order):
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

    @staticmethod
    def sensor_checker(rule, status, order):
        """
        Sensor-type rule checking handler. Push to IoTTalk server accordingly.

        Args:
            rule: UserRule entity stored in memory.
            status: CB_Status entity stored in memory.
            order: Which pair of (actuator, sensor) mappings is being checked.

        Returns:
            None
        """
        sensor_df = 'Threshold-O' + str(order)
        data = DAN.pull(sensor_df)
        if data is None:
            return

        data = data[0]
        status.value = data
        actuator_df = 'Trigger-I' + str(order)
        
        try:
            if 'notset' in rule.comparison_open and 'notset' in rule.comparison_close:
                if status.status == 'RED':
                    DAN.push(actuator_df, 0)
                status.status = 'GREEN'
            elif 'notset' in rule.comparison_open:
                satisfied = self.condition_handler[rule.comparison_close](data, rule.threshold_close)
            elif 'notset' in rule.comparison_close:
                satisfied = self.condition_handler[rule.comparison_open](data, rule.threshold_open)
            else:
                satisfied = self.condition_handler[rule.comparison_close](data, rule.threshold_close)
                satisfied = self.condition_handler[rule.comparison_open](data, rule.threshold_open)

            if satisfied:
                
        except Exception as err:
            print(err)
        

    def bigger(data, threshold):
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

    def smaller(data, threshold):
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

    def bigger_equal(data, threshold):
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

    def smaller_equal(data, threshold):
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



sa = AG_SA('{cb_id}', {config}, '{mac_addr}')

sa.connect_db()
sa.recover()


while True:
   sa.check_rules()
   time.sleep(5)
