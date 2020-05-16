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

    def push(self, actuator, value):
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
