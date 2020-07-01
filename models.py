import datetime


from pony.orm import Database
from pony.orm import Required
from pony.orm import PrimaryKey
from pony.orm import Optional
from pony.orm import Set
from pony.orm import db_session


cb_db = Database()


class UserRule(cb_db.Entity):
    rule_id = PrimaryKey(int, auto=True)  # For AG_SA to write status.
    rule_type = Required(str)  # Sensor / Timer.
    actuator_alias = Required(str)  # Alias of the actuator in this rule.
    sensor_alias = Optional(str)  # Alias of the actuator in this rule, required if rule_type is 'sensor'.
    threshold_open = Optional(float)  # Sensor value to decide trigger actuator or not.
    threshold_close = Optional(float)  # Sensor value to decide close actuator or not.
    comparison_open = Optional(str)  # Comparison method to decide trigger actuator or not.
    comparison_close = Optional(str)  # Comparison method to decide close actuator or not.
    time_open = Optional(datetime.time)  # Trigger actuator every when current time exceeds time_open.
    time_close = Optional(datetime.time)  # Close actuator every when current time exceeds time_open.
    exetime = Optional(int)  # execution time for periodically execution
    sa = Required("CB_SA")  # which SA it belongs to

    @classmethod
    @db_session
    def update_rules(cls, **kwargs):
        print('db', kwargs)
        rule = cls.get(actuator_alias=kwargs['actuator_alias'])
        if rule is None:
            UserRule(rule_type=kwargs['rule_type'], actuator_alias=kwargs['actuator_alias'])
            rule = cls.get(actuator_alias=kwargs['actuator_alias'])

        rule.set(**kwargs)

        return

    @classmethod
    @db_session
    def delete_actuator_alias(cls, alias):
        rule = cls.get(actuator_alias=alias)
        if rule is None:
            return
        rule.delete()
        return

    @classmethod
    @db_session
    def delete_sensor_alias(cls, alias):
        rule = cls.get(sensor_alias=alias)
        if rule is None:
            return
        rule.delete()
        return

    @classmethod
    @db_session
    def select_all(cls):
        return cls.select()[:]


class CB_SA(cb_db.Entity):
    cb_id = PrimaryKey(int, auto=True)  # id of this SA.
    cb_name = Required(str)  # User-defined cb_name. Can be repeated.
    rule_set = Set(UserRule)
    account_set = Set("CB_Account")  # accounts that can access this SA.


class CB_Account(cb_db.Entity):
    account = Required(str)  # Account of this user.
    privilige = Required(int)  # User level of this user.
    sa_set = Set(CB_SA)  # SAs this user can see.


class CB_Status(cb_db.Entity):
    rule_id = Required(int)  # For Subsystem to findout which rule this status entry represent.
    status = Required(str)  # The status of the corresponding rule, should be 'red'/'yellow'/'green'.
    value = Required(float)  # The sensory value received from IoTtalk.
