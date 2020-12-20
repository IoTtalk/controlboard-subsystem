import datetime


from pony.orm import Database
from pony.orm import Required
from pony.orm import PrimaryKey
from pony.orm import Optional
from pony.orm import Set
from pony.orm import LongStr


cb_db = Database()


class UserRule(cb_db.Entity):
    rule_id = PrimaryKey(int, auto=True)  # For AG_SA to write status.
    actuator_alias = Required(str)  # Alias of the actuator in this rule.
    actuator_df = Required(str)  # Device Feature Name of the actuator in this rule.
    sensor_alias = Optional(str)  # Alias of the actuator in this rule.
    sensor_df = Optional(str)  # Device Feature Name of sensors in this rule.
    sensor_index = Optional(int)  # Which Sensor this rule is using currently.
    df_order = Required(int)  # Which IDF/ODF pair to pull/push data.
    threshold_open = Optional(float)  # Sensor value to decide trigger actuator or not.
    threshold_close = Optional(float)  # Sensor value to decide close actuator or not.
    comparison_open = Optional(str)  # Comparison method to decide trigger actuator or not.
    comparison_close = Optional(str)  # Comparison method to decide close actuator or not.
    time_open = Optional(datetime.time)  # Trigger actuator every when current time exceeds time_open.
    time_close = Optional(datetime.time)  # Close actuator every when current time exceeds time_open.
    period = Required(int)  # Period functionality.
    exetime = Optional(int)  # execution time for periodically execution.
    mode = Required(str)  # Sensor/Timer/On/Off.
    weekday = Optional(str)  # Weekdays this rule should be executed.
    duty_pos = Optional(int)  # Positive edge of Duty Cycle.
    duty_neg = Optional(int)  # Negative edge of Duty Cycle.
    sa = Required("CB_SA")  # which SA this rule belongs to.


class CB(cb_db.Entity):
    cb_id = PrimaryKey(int, auto=True)
    cb_name = Required(str)
    sa_set = Set("CB_SA", cascade_delete=True)
    shared = Required(bool)
    account_set = Set("CB_Account")  # accounts that can access this SA.
    icon = Required(str)


class CB_SA(cb_db.Entity):
    sa_id = PrimaryKey(int, auto=True)  # id of this SA.
    sa_name = Required(str)  # User-defined cb_name. Can be repeated.
    pinned = Required(bool)  # if this SA is pinned.
    cb = Required(CB)  # which CB this SA belongs to.
    ag_token = Required(LongStr)  # AG-returned token
    mac_addr = Required(LongStr)  # Mac-addr of this SA
    rule_set = Set(UserRule, cascade_delete=True)
    p_id = Required(int)  # project id of this SA
    do_id = Required(str)  # device object id for this SA.


class CB_Account(cb_db.Entity):
    account = Required(str)  # Account of this user.
    privilege = Required(int)  # User level of this user.
    cb_set = Set(CB)  # CBs this user can see.
