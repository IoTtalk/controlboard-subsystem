import datetime


from pony.orm import Database, Required, Optional, db_session, Json, StrArray


from config import env_config


cb_db = Database('sqlite', env_config.sqlite_rule_db, create_db=True)


class UserRule(cb_db.Entity):
    rule_type = Required(str)
    actuator_alias = Required(str)
    sensor_alias = Optional(str)
    threshold_open = Optional(float)
    threshold_close = Optional(float)
    comparison_open = Optional(str)
    comparison_close = Optional(str)
    time_open = Optional(datetime.time)
    time_close = Optional(datetime.time)
    exetime = Optional(int)


    @classmethod
    @db_session
    def update_rules(cls, **kwargs):
        print ('db', kwargs)
        rule = cls.get(actuator_alias=kwargs['actuator_alias'])
        if rule is None:
            UserRule(rule_type=kwargs['rule_type'], actuator_alias=kwargs['actuator_alias'])
            rule = cls.get(actuator_alias=kwargs['actuator_alias'])

        rule.set(**kwargs)

        return

    @classmethod
    @db_session
    def select_all(cls):
        return cls.select()[:]


class CBInstance(cb_db.Entity):
    cb_id = Required(str) # all uuids should be converted to strings at first!
    mappings = Required(Json)
    rule_ids = Required(StrArray) # rule_ids should be transformed from UUID to strings!


class Account(cb_db.Entity):
    account = Required(str)
    keyword = Required(str)
    cb_ids = Optional(StrArray)
