
'''
rule_info: User-defined rules in dictionary to avoid huge querying rules resulting from pulling-threads
{
  actuator_alias1: {
      "rule_type": "timer" or "sensor", required
      "actuator_alias": string, required
      "sensor_alias": string, required if Type is "sensor"
      "threshold_close": integer, required if Type is "sensor"
      "threshold_open": integer, required if Type is "sensor"
      "comparison_close": string, required
      "comparison_open": string, required
      "time_open": datetime string, required if Type is "timer"
      "time_close": datetime string, required if Type is "timer"
      "trigger": whether this actuator is triggered or not
  },
  ...
}
'''
rule_info = dict()

# variables used in part-2: checking actuator succeeded
df_hist_val = dict()
df_hist_len = dict()


'''
dict with the following format
  {
    'actuator_alias1': (sensor_alias, order on IoTTalk GUI)
  }
'''
mappings = dict()

# collection of pushing-threads, used in individual controling of each pulling-thread is needed
pushing_thread_dict = dict()

# currently we use this flag to determine if all pushing-threads should terminate
pushing_flag = True
pulling_flag = True
