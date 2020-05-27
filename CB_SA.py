

from uuid import uuid4
from datetime import datetime, date, timedelta

from utils import condition_handler

from CB_DA import CB_DA


class CB_SA():
    def __init__(self, usr_session, owner, logger, sa_id=None, sa_name=None):
        '''
        Initialization of a CB SA

        Args:
            usr_session: current logined user's CCM session
            owner: Account of the user who owns this CB SA.
            sa_id: If specified, use this ID to recover a previous created CB SA from Database.
            sa_name: If specified, use this name as the name of this SA in log. Else use sa_id instead

        Class variables:
            rules: User-defined rules in dictionary to avoid huge querying rules resulting from checking rule satisfaction.
            {
                actuator_alias1:
                {
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
                }
            }
            mappings: A dictionary of the following format.
            {
                'actuator_alias1': (sensor_alias1, DF order on IoTTalk GUI)
            }
            da: Registered DA for this SA.
            logger: Logger for this SA to write checking and pushing logs.
            sa_id: ID for this SA, used in Database querying.
            sa_name: Name for this SA, used for user-friendly management and logs.
            df_hist_val: History values of sensors manipulated by this SA.
            df_hist_len: # recorded history values.

        Returns:
            None
        '''
        self.rules = dict()
        self.mappings = dict()
        self.da = CB_DA(usr_session)  # DA for this SA
        self.logger = logger
        self.df_hist_val = dict()
        self.df_hist_len = dict()

        if sa_id is None:
            self.sa_id = uuid4()
        else:
            self.sa_id = sa_id

        if sa_name is None:
            self.sa_name = self.sa_id
        else:
            self.sa_name = sa_name

        return

    def terminate(self):
        '''
        Termination of this CB SA.

        Args:
            None.

        Returns:
            Boolean indicating termination succeed or failed.
        '''

        pass

    def check_rules(self):
        '''
        Rule checker for all rules set for this SA.
        Called by Subsystem every check period.

        Args:
            None

        Returns:
            None
        '''
        for rule in self.rules:
            if rule.rule_type == "timer":
                CB_SA.time_checker(self.da, self.logger, rule)
            else:
                CB_SA.sensor_handler(self.da, self.logger, rule)

        return

    def update_rules(self, actuator_alias, rule):
        '''
        Update open/close rule for designated  actuator

        Args:
            actuator_alias: the alias of the actuator whose rule is to be updated.
            rule: rule content to be applied to the actuator.

        Returns:
            Boolean indicating rule update procedure succeed or failed.
        '''

        return True

    @staticmethod
    def sensor_checker(comparison, threshold, data, action, actuator_alias, sensor_alias):
        """
        Sensor-type rule checking worker.

        Args:
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
        avg = sum(list(utils.df_hist_val[sensor_alias])) / len(utils.df_hist_val[sensor_alias])
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

    @staticmethod
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
        current = datetime.now()
        actuator_name = 'Trigger' + '-I' + str(order + 1)
        time_open = datetime.combine(date.today(), utils.rule_info[actuator_alias]['time_open'])
        time_close = datetime.combine(date.today(), utils.rule_info[actuator_alias]['time_close'])
        exetime = utils.rule_info[actuator_alias]['exetime']

        if time_open > time_close:
            time_close = time_close + timedelta(days=1)

        if exetime == 0:  # timer set to not set
            if utils.rule_info[actuator_alias]['trigger'] is True:
                da.push(actuator_name, 0)
                utils.rule_info[actuator_alias]['trigger'] = False
                self.logger.info(f'disable timer to close {actuator_alias}')
        else:
            if current > time_open and current < time_close:
                if utils.rule_info[actuator_alias]['trigger'] is False:
                    utils.rule_info[actuator_alias]['trigger'] = True
                    self.da.push(actuator_name, 1)
                utils.rule_info[actuator_alias]['status'] = 'red'
                self.logger.info(f'timer trigger {actuator_alias}, current time: {current} rule start time: {time_open} rule end time: {time_close}')
            else:
                if utils.rule_info[actuator_alias]['trigger'] is True:
                    utils.rule_info[actuator_alias]['trigger'] = False
                    self.da.push(actuator_name, 0)
                if abs((time_open - current).total_seconds()) < 600 and time_open > current:
                    utils.rule_info[actuator_alias]['status'] = 'yellow'
                else:
                    utils.rule_info[actuator_alias]['status'] = 'green'
                self.logger.info(f'timer close {actuator_alias}, current time: {current} rule start time: {time_open} rule end time: {time_close}')

        return

    @staticmethod
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
                self.logger.info(f'Change all comparison to notset, close actuator {actuator_alias} and corresponding pushing thread')
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
                self.logger.info(f'sensor {sensor_alias} close {actuator_alias}, comparison: {comparison_close}, threshold: {threshold_close}, data pulled: {data}')
                utils.rule_info[actuator_alias]['trigger'] = False

            elif to_trigger == 'OPEN':
                if utils.rule_info[actuator_alias]['trigger'] is False:
                    self.da.push(actuator_name, 1)
                self.logger.info(f'sensor {sensor_alias} trigger {actuator_alias}, comparison: {comparison_open}, threshold: {threshold_open}, data pulled: {data}')
                utils.rule_info[actuator_alias]['trigger'] = True

            print(utils.rule_info[actuator_alias]['trigger'], actuator_alias)
        except Exception as ep:
            self.logger.error(ep)

        return
