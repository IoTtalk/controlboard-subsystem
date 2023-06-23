import re, time, json, threading, requests, traceback
import datetime
import paho.mqtt.client as mqtt
import DAN
import random 
from time import perf_counter

def df_func_name(df_name):
    return re.sub(r'-', r'_', df_name)

def Dummy_Sensor():
    # return random.randint(25, 30)

    # for sensor
    #print("idf data : ", time.time())
    return time.time()

total = counter = 0
def Dummy_Control(data: list):
    global total, counter

    # for sensor
    if data[0] != 0:
        #print("data[0] : ", data[0])
        delta = time.time() - (data[0]-10001)
        # if delta < 0.1:
        total += delta
        counter += 1
        print('{}: {}'.format(counter, delta))
        if counter%50 == 0:
            print('\n                    Average: {}\n'.format(total/counter * 1000))

    # for manual
    # counter += 1
    # print('{}: {}'.format(counter, time.time()*1000))

ServerURL = 'http://5.iottalk.tw:9999' #For example: 'https://iottalk.tw'
MQTT_broker = '5.iottalk.tw' # MQTT Broker address, for example:  'iottalk.tw' or None = no MQTT support
# MQTT_broker = None
MQTT_port = 5566
MQTT_encryption = True
MQTT_User = 'iottalk'
MQTT_PW = 'iottalk2023'

device_model = 'Dummy_Device'
IDF_list = ['Dummy_Sensor']
ODF_list = ['Dummy_Control']
device_id = None #if None, device_id = MAC address
if device_id == None: device_id = DAN.get_mac_addr()
device_name = 'dummy_cb'
exec_interval = 0.1  # IDF/ODF interval

IDF_funcs = {}
for idf in IDF_list:
    IDF_funcs[idf] = globals()[df_func_name(idf)]
ODF_funcs = {}
for odf in ODF_list:
    ODF_funcs[odf] = globals()[df_func_name(odf)]

def on_connect(client, userdata, flags, rc):
    print("on connect is working~")
    print("rc : ", rc)
    if not rc:
        print('MQTT broker: {}'.format(MQTT_broker))
        if ODF_list == []:
            print('ODF_list is not exist.')
            return
        topic_list=[]
        for odf in ODF_list:
            topic = '{}//{}'.format(device_id, odf)
            topic_list.append((topic,0))
        if topic_list != []:
            r = client.subscribe(topic_list)
            if r[0]: print('Failed to subscribe topics. Error code:{}'.format(r))
    else: print('Connect to MQTT borker failed. Error code:{}'.format(rc))
        
def on_disconnect(client, userdata,  rc):
    print('MQTT Disconnected. Re-connect...')
    client.reconnect()

def on_message(client, userdata, msg):
    samples = json.loads(msg.payload)
    ODF_name = msg.topic.split('//')[1]
    if ODF_funcs.get(ODF_name):
        ODF_data = samples['samples'][0][1]
        ODF_funcs[ODF_name](ODF_data)
    else:
        print('ODF function "{}" is not existed.'.format(ODF_name))

def mqtt_pub(client, deviceId, IDF, data):
    topic = '{}//{}'.format(deviceId, IDF)
    sample = [str(datetime.datetime.today()), data]
    payload  = json.dumps({'samples':[sample]})
    status = client.publish(topic, payload)
    if status[0]: print('topic:{}, status:{}'.format(topic, status))

def on_register(r):
    print('Server: {}\nDevice name: {}\nRegister successfully.'.format(r['server'], r['d_name']))

def MQTT_config(client):
    client.username_pw_set(MQTT_User, MQTT_PW)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    if MQTT_encryption: client.tls_set()
    client.connect(MQTT_broker, MQTT_port, keepalive=60)


DAN.profile['dm_name'] = device_model
DAN.profile['df_list'] = IDF_list + ODF_list  
if device_name: DAN.profile['d_name']= device_name
if MQTT_broker: DAN.profile['mqtt_enable'] = True


start = perf_counter()
result = DAN.device_registration_with_retry(ServerURL, device_id)
print("---- : ", perf_counter()-start)

print("result : ", result)
on_register(result)

if MQTT_broker:
    mqttc = mqtt.Client()
    MQTT_config(mqttc)
    mqttc.loop_start()

while True:
    try:
        # print("\n---- start ----\n")
        
        for idf in IDF_list:
            if not IDF_funcs.get(idf): 
                print('IDF function "{}" is not existed.'.format(idf))
                continue
            # start = perf_counter()
            IDF_data = IDF_funcs.get(idf)()
            if not IDF_data: continue
            if type(IDF_data) is not tuple: IDF_data=[IDF_data]
            if MQTT_broker: 
                # print("\nset MQTT_broker, IDF_data : ", IDF_data,"\n")
                mqtt_pub(mqttc, device_id, idf, IDF_data)
            else: 
                DAN.push(idf, IDF_data)
            # print("--- after push : ", perf_counter()-start)
            time.sleep(0.001)

        if not MQTT_broker: 
            for odf in ODF_list:
                if not ODF_funcs.get(odf): 
                    print('ODF function "{}" is not existed.'.format(odf))
                    continue
                ODF_data = DAN.pull(odf)
                if not ODF_data: continue
                ODF_funcs.get(odf)(ODF_data)
                time.sleep(0.001)


    except Exception as e:
        if str(e).find('mac_addr not found:') != -1:
            print('Reg_addr is not found. Try to re-register...')
            DAN.device_registration_with_retry(ServerURL, device_id)
        else:
            exception = traceback.format_exc()
            print(exception)
            if MQTT_broker: mqttc.reconnect()
            time.sleep(1)    

    time.sleep(exec_interval)

