from models import UserRule

class CB_Instance(object):
    def __init__(self, uuid, proj_info):
        # proj_info: {sensor1: actuator1, sensor2: actuator2, ...}
        self.id = uuid
        self.proj_info = proj_info
        # self.rules = UserRule.select(lambda rule: rule.)
