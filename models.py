import datetime


from pony.orm import Database, Required, Optional, db_session


from config import env_config


rule_db = Database('sqlite', env_config.sqlite_rule_db, create_db=True)


class UserRule(rule_db.Entity):
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
