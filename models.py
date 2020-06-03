import datetime
import uuid.UUID


from pony.orm import Database
from pony.orm import Required
from pony.orm import Optional
from pony.orm import Set
from pony.orm import db_session
from pony.orm.ormtypes import StrArray


cb_db = Database()


class UserRule(cb_db.Entity):
    rule_type = Required(str) # Sensor / Timer.
    actuator_alias = Required(str) # Alias of the actuator in this rule.
    sensor_alias = Optional(str) # Alias of the actuator in this rule, required if rule_type is 'sensor'.
    threshold_open = Optional(float) # Sensor value to decide trigger actuator or not.
    threshold_close = Optional(float) # Sensor value to decide close actuator or not.
    comparison_open = Optional(str) # Comparison method to decide trigger actuator or not.
    comparison_close = Optional(str) # Comparison method to decide close actuator or not.
    time_open = Optional(datetime.time) # Trigger actuator every when current time exceeds time_open.
    time_close = Optional(datetime.time) # Close actuator every when current time exceeds time_open.
    exetime = Optional(int) # 

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
    cb_id = Required(UUID) # uuid of this SA.
    cb_name = Required(str) # User-defined cb_name. Can be repeated. 
    avail_account = Set('CB_Account', reverse='account') # Accounts that can access this SA.


class CB_Account(cb_db.Entity):
    account = Required(str) # Account of this user.
    privilige = Required(int) # User level of this user.
    avail_sa = Set(CB_SA, reverse=cb_id) # SAs this user can see.

