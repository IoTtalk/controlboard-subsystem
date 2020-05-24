import DAN


class CB_DA():
    def __init__(self, usr_session):
        '''
        TODO:
            1. Create IoTTalk Project
            2. Register device model instance and bind.
            3.
        '''
        pass

    @staticmethod
    def push(actuator, value):
        '''
        Push value passed from SA to actuator on IoTTalk server.

        Args:
            actuator: the name of the actuator. Notice that it's NOT the alias of the actuator.
            value: what is desired to be pushed to IoTTalk Server.

        Returns:
            None
        '''
        DAN.push(actuator, value)

        return

    @staticmethod
    def pull(sensor_list, logger):
        """
        Pull sensor value from IoTTalk server.

        Args:
            sensor_list: pair of (sensor_alias, sensor_name).
            logger: log of this SA.

        Returns:
            sensor_data: a dictionary of sensor_alias with data
            {
                'sensor_alias': data
            }
        """
        sensor_data = dict()
        try:
            for sensor_alias, sensor_name in sensor_list:
                data = DAN.pull(sensor_name)
                sensor_data[sensor_alias] = data[0]
                if data is not None:
                    logger.info(f"Pull data {data[0]} from {sensor_alias}")
        except Exception as ep:
            logger.warn(ep)

        return sensor_data
