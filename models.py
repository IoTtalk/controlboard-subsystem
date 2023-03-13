import datetime


from pony.orm import Database
from pony.orm import Required
from pony.orm import PrimaryKey
from pony.orm import Optional
from pony.orm import Set
from pony.orm import LongStr


cb_db = Database()

class CB(cb_db.Entity):
    cb_id = PrimaryKey(int, auto=True)  # id of this SA.
    cb_name = Required(str)  # User-defined cb_name. Can't be repeated.
    status = Required(bool)  # This CB's current status, True => working, False => in maintanance.
    ag_token = Required(LongStr)  # AG-returned token
    mac_addr = Required(LongStr)  # Mac-addr of this SA
    p_id = Required(int)  # project id of this SA
    do_id = Required(str)  # device object id for this SA.
    na_id = Required(str)  # na_ids used in delete CB
    dedicated = Required(bool)  # If this CB is created for ControlBoard

    # Related
    rule_set = Set("CBElement", cascade_delete=True)
    account_set = Set("CB_Account")

class CBElement(cb_db.Entity):
    rule_id = PrimaryKey(int, auto=True)  # For AG_SA to write status.
    actuator_alias = Required(str)  # Alias of the actuator in this rule.
    actuator_df = Required(str)  # Device Feature Name of the actuator in this rule.
    # sensor_alias = Optional(str)  # Alias of the sensors in this rule.
    # sensor_df = Optional(str)  # Device Feature Name of sensors in this rule.
    # sensor_index = Optional(int)  # Which Sensor this rule is using currently.
    df_order = Required(int)  # Which IDF/ODF pair to pull/push data.
    # threshold_open = Optional(float)  # Sensor value to decide trigger actuator or not.
    # threshold_close = Optional(float)  # Sensor value to decide close actuator or not.
    # comparison_open = Optional(str)  # Comparison method to decide trigger actuator or not.
    # comparison_close = Optional(str)  # Comparison method to decide close actuator or not.
    time_open = Optional(datetime.time)  # Trigger actuator every when current time exceeds time_open.
    time_close = Optional(datetime.time)  # Close actuator every when current time exceeds time_open.
    mode = Required(str)  # Sensor/Timer/On/Off.
    weekday = Optional(str)  # Weekdays this rule should be executed.  ranging from 0 to 6
    duty_pos = Optional(int)  # Positive edge of Duty Cycle.
    duty_neg = Optional(int)  # Negative edge of Duty Cycle.
    #operation = Optional(str) # "AND"/"OR" operations for CB_Sensors in order.

    # Related
    cb = Required("CB")  # which CB this rule belongs to.
    sensor_set = Set("CB_Sensor", cascade_delete=True)

# CBElement Sensors
class CB_Sensor(cb_db.Entity):
    sensor_id = PrimaryKey(int, auto=True) # id of this ???
    sensor_alias = Optional(str)  # Alias of the sensors in this rule.
    sensor_df = Optional(str)  # Device Feature Name of sensors in this rule.
    sensor_index = Optional(int)  # Which Sensor this rule is using currently.
    threshold_open = Optional(float)  # Sensor value to decide trigger actuator or not.
    threshold_close = Optional(float)  # Sensor value to decide close actuator or not.
    comparison_open = Optional(str)  # Comparison method to decide trigger actuator or not.
    comparison_close = Optional(str)  # Comparison method to decide close actuator or not.
    operation = Optional(str) # "AND"/"OR" operations for CB_Sensors in order.
    is_show_operation = Optional(bool) # will show operations for CB_Sensors or not.

    # Related
    cbelement = Required("CBElement") # which CBElement this rule belongs to.

class CB_Account(cb_db.Entity):
    account = Required(str)  # Account/Email of this user.
    user_name = Required(str)  # UserName of this user
    privilege = Required(int)  # User level of this user. Note that the managers call this column `identity`
    access_token = Required(str)  # Account Access token for this user.
    cb_set = Set(CB)  # CBs this user can see.
