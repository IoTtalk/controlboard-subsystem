class EnvironmentConfig():
    host = '0.0.0.0'
    port = 7789
    df_his_record_len = 200
    max_thresholds = 5
    sqlite_rule_db = 'UserRule.sqlite'
    server_ip = 'http://140.113.199.182:9999'
    mac_addr = 'ALIASTESTING'
    ctlboard_profile = {
        'd_name': 'DMTEST',
        'dm_name': 'ControlBoard',
        'u_name': 'yb',
        'is_sim': False,
        'df_list': ['Threshold-O1', 'Trigger-I1', 'Threshold-O2', 'Trigger-I2',
                    'Threshold-O3', 'Trigger-I3', 'Threshold-O4', 'Trigger-I4',
                    'Threshold-O5', 'Trigger-I5']
    }


env_config = EnvironmentConfig()
