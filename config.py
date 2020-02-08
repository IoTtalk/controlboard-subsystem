import logging

class EnvironmentConfig():
    host = '0.0.0.0'
    port = 7789
    df_his_record_len = 200
    max_thresholds = 5
    sqlite_rule_db = 'UserRule.sqlite'
    server_ip = 'http://140.113.199.182:9999'
    mac_addr = 'CB_Subsystem'
    ctlboard_profile = {
        'd_name': 'ControlBoard',
        'dm_name': 'ControlBoard',
        'u_name': 'yb',
        'is_sim': False,
        'df_list': ['Threshold1-O', 'Trigger1-I', 'Threshold2-O', 'Trigger2-I',
                    'Threshold3-O', 'Trigger3-I', 'Threshold4-O', 'Trigger4-I',
                    'Threshold5-O', 'Trigger5-I']
    }



env_config = EnvironmentConfig()
