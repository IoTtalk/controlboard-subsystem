# ControlBoard Subsystem
###### tags: `IoTtalk` `python` `flask` `Workflow`

## Installation

### System Requirements
- `python >= 3.6`
- Two ports for Flask Server/ZMQ respectively (default 7789, 7790)
- AG Subsystem with the following packages installed
    - PonyORM
    - pymysql
    - ZMQ
    - `pip install pymysql pony zmq`
- IoTtalk Server compatible with CCM API
- (optional) MySQL server

The following commands assume your OS is Linux.

### Setup Environment
1. Create virtual environment 
    ```
    python -m venv cbvenv
    source cbvenv/bin/activate
    ```
2. Install required packages 
    ```
    pip install -r requirements.txt
    (optional)pip install -r test-requirements.txt
    ```

### Setup ControlBoard Subsystem
1. Enter to ControlBoard Subsystem directory
2. Modify the settings in `Config.ini`
    Below's code is an example of Config.ini, **settings that can be retained will be mentioned in its' above comment correspondingly.**
    ```ini
    [IoTtalk]
    # IoTtalk Server IP
    ServerIP = 140.113.199.182

    # IoTtalk Server Port
    Port = 9999

    # Use v1 or v2, currently only v1 is supported
    version = 1

    [env]
    # Root directory to save logs. Can be retained
    LogRoot = ./logs

    # CB Subsystem's Public IP address.
    host = 140.113.63.25

    # CB Subsystem's port.
    port = 7789

    # AG Subsystem's Public IP address.
    host_ag = 140.113.215.12

    # AG Subsystem's port.
    port_ag = 8000

    # Port for SA Status Collector
    port_zmq = 7790

    # Root directory to save custom icons. Can be retained
    icon_path = ./static/imgs

    # Default ControlBoard icon. Can be retained
    default_icon = 0_landscape.svg

    # Accepted icon extensions. Can be retained
    icon_extensions = png,svg

    # Default Admin account. Can be retained
    admin = admin
    
    # Email Notifier Sender
    sender = ControlBoard@iottalk.tw

    # Email Title
    title = Manual operation notification

    [db]
    # use MySQL or SQLlite
    database = mysql

    # MySQL Server IP
    host = 140.113.215.12

    # MySQL Server Port
    port = 3306

    # User name for MySQL Server
    user = cbsubsystem

    # Password for MySQL Server
    pwd = pcs54784

    # DB name for MySQL Server
    dbname = controlboard

    # Whether to reset db, 0 or 1
    reset = 1
    ```
3. Start the subsystem
    ```
    python CB_Subsystem.py Config.ini
    ```


## Usage [Not Done Yet]

### ControlBoard
ControlBoard Subsystem uses **Field** as it's basic control unit.

A Field represents an IoTtalk project and contains several *NA*s that are created in the IoTtalk GUI. One can decide how to manage his/her sensors/actuators using Fields at their convenience.

For example, one can put sensors/actuators that are geographically close to each other into same Fields, or place sensor/actuators with the same functionalities into one Field.

A **ControlBoard** is consisted of Fields and is viewed as an **logical Field** that may contain many different types of sensors/actuators installed at different places.


### Management
The management of ControlBoard Subsystem is consisted of two parts, ControlBoard management and User privilege management.

#### ControlBoard Management
ControlBoard management supports the following operations

* ControlBoard Creation
* ControlBoard Deletion
* Change ControlBoard Icon

ControlBoards can have the same naming

ControlBoard supports cascade-delete, namely when you delete a ControlBoard, the Fields inside will also be destoryed.

#### User Privilege Management


Users are divided into three groups, *`User`*, *`Superuser`* and *`Admin`*.

A *`User`* level user can only view ControlBoards that a *`Superuser`* or *`Admin`* user granted him/her to control, and is not allowed to enter the Management page of CB Subsystem.


## API List
List of ControlBoard Subsystem APIs.

### **Field Related**

#### *[POST] /sa/<sa_id>/new_rules*
**Description**：

*Login Required*
Configure that in what situation should the specified actuator be opened or closed.

**Parameters**：

| Name | Data type | Description |
|-|-|-|
| sa_id | Integer | The ID of the field to save UserRules, passed through url |
| rule_setting | List of Json | The UserRules' content, passed through request body |

The following table illustrates the content of *rule_settings*

| Name | Data type | Description |
|-|-|-|
| actuator_alias | String | The alias on IoTTalk GUI of a actuator device feature | "FAN" | required |
 mode | String | Type of this UserRule. Should be one of  ON/OFF/Sensor/Timer | required if type="sensor" |
| sensor_index | Integer | Index of usable sensors in this UserRule |
| threshold_open | Integer | Threshold value to open the corresponding actuator |
| threshold_close | Integer | Threshold value to close the corresponding actuator |
| comparison_open | String | Comparison method for a condition to open actuator |
| comparison_close | String | Comparison method for a condition to close actuator |
| time_open | List containing three Integers | Starting time in "%H:%M:%S" 24-h format for a timer type condition |
| time_close | List of length three | Ending time in "%H:%M:%S" 24-h format for a timer type condition |
| duty_pos | Integer | PosEdge frequency of the Duty Cycle module |
| duty_neg | Integer | NegEdge frequency of the Duty Cycle module |
| weekday | List of Integers | Weekdays that this UserRule is allowed to execute. |


**Request body example**
```json=
[
    {
        "actuator_alias": "Dummy_Control",
        "mode": "Sensor",
        "sensor_index": 1,
        "threshold_open": 6,
        "threshold_close": 3,
        "comparison_open": "bigger",
        "comparison_close": "smaller",
        "time_open": [0, 0, 0],
        "time_close": [0, 0, 0],
        "duty_pos": 1800,
        "duty_neg": 30,
        "weekday": [4, 5]
    },
    {
        "actuator_alias": "Dummy_Control",
        "mode": "Timer",
        "sensor_index": 1,
        "threshold_open": 6,
        "threshold_close": 3,
        "comparison_open": "bigger",
        "comparison_close": "smaller",
        "time_open": [8, 30, 0],
        "time_close": [17, 0, 0],
        "duty_pos": 1800,
        "duty_neg": 30,
        "weekday": [4, 5]
    }
]
```

**Response**：

| Field | Data type | description | 
|-|-|-|
| msg | String | Detailed setup status |
| status | Integer | Corresponding HTTP status code |

**Response example**
```json=
// Success
{
    "status": 200,
    "msg": "Configuration Saved."
}

// Invalid UserRule detected
{
    "status": 400,
    "msg": A string containing detected actuators
}

// Failed at registering another AG-SA
{
    "status": 500,
    "msg": "Internal Server Error"
}
```

---


#### *[GET] /sa/<sa_id>/rules*
**Description**

*Login Required*
Get the rules contained in the specified Field.

**Parameter**

| Name | Data type | Description |
|-|-|-|
| sa_id | Integer | The ID of the field to get UserRules, passed through url |


**Response**：

| Field | Data type | description | 
|-|-|-|
| rule_list | List of Jsons | UserRules saved in this Field |



##### The following table illustrates the content of each element in *rule_list*
| Field | Data type | description | 
|-|-|-|
| ruleID | Integer | Unique ID of this UserRule |
| actuator | String | User-defined actuator df-alias on IoTtalk GUI |
| sensors | List of Strings | User-defined sensor df-alias on IoTtalk GUI |
| mode | String | Indicating the mode of this UserRule, should be one of ON/OFF/Sensor/Timer |
| content | Json | The UserRule's content, fields explained in the next table  |
| dirty | boolean | Indicating if this UserRule is modified but not saved. Dummy data for frontend rendering here |
| prevTrigger | Integer | Previous triggered epoch time of the actuator controlled by this UserRule. Dummy data for frontend rendering here |
| status | boolean | Indicating the status of the actuator controlled by this UserRule. Dummy data for frontend rendering here |
| time | String in format "HH:MM" | Standard Time of the AG Server. Dummy data for frontend rendering here |
| value | Integer | Current selected sensor value of this UserRule. Dummy data for frontend rendering here |

##### The following table illustrates the *content* field in each element of *rule_list*
| Field | Data type | description | 
|-|-|-|
| openSensor | String | One of bigger/smaller/null |
| openSensorVal | Integer | Threshold value to trigger the actuator |
| closeSensor | String | One of bigger/smaller/null |
| closeSensorVal | Integer |  Threshold value to close the actuator |
| openTimer | List of length 3 | The timing allowed to trigger the actuator |
| closeTimer | List of length 3 | The timing allowed to close the actuator |
| dutyPos | Integer | Seconds representing the positive cycle length of one Duty cycle.
| dutyNeg | Integer | seconds representing the negative cycle length of one Duty cycle.
| weekdays | List of Integers | Integers representing weekdays. Mon <=> 0, Sun <=> 6, All <=> 7


**Return example**
```json=
[
  {
    "ruleID": 1
    "actuator": "Dummy_Control"
    "sensors": ["Drip", "Humid"],
    "mode": "Sensor",
    "dirty": False,
    "prevTrigger": -10000,
    "status": False,
    "time": "00:00",
    "value": 0
    "content": {
        "openSensor": "bigger", 
        "openSensorVal": 0,
        "closeSensor": "smaller",
        "closeSensorVal": 10,
        "openTimer": [0,0,0],
        "closeTimer": [0,0,0],
        "dutyPos": 15,
        "dutyNeg": 15,
        "weekdays": [0, 1, 3]
    }
  }
]
```

---

#### *[GET] /sa/<sa_id>/current_data*

**Description**

*Login Required*
Get the current data(actuatos's status, sensor value, previous triggered time-stamp) of UserRules contained in the specifed Field.

**Parameters**
| Field | Data type | description | 
|-|-|-|
| sa_id | Integer | The ID of the field to get UserRules' execution status, passed through url |

**Response**：

| Field | Data type | description | 
|-|-|-|
| res_dict | Dictionary of Jsons | Execution status of UserRules in this Field |


##### The following table illustrates the content of each element in *res_dict*
| Field | Data type | description | 
|-|-|-|
| rule_id | Integer | Unique ID of this rule |
| status | String | Status of this UserRule, should be one of "RED"(Triggered)/"Green"(Closed)/"Yellow"(About to be triggered)
| prev_trigger | Float | Epoch time that this UserRule triggered last time |
| value | Float | Value received from IoTtalk Server |

**Response Example**
```json=
{
    1: {
        "rule_id": 1,
        "status": "RED",
        "prev_trigger": 123.456789,
        "value": 123.4
    },
    4: {
        "rule_id": 4,
        "status": "GREEN",
        "prev_trigger": 4567,
        "value": 81000
    }
}
```

---

#### *[GET] /sa/refresh_sa/<sa_id>*

**Description**
Refetch the actuators and sensors and update the UserRules according to those sensors/actuators.

*comment the `time.sleep` in this function if your IoTtalk Server can handle continous requests*

**Parameters**
| Field | Data type | description | 
|-|-|-|
| sa_id | Integer | The ID of the field to be refreshed, passed through url |

**Response**：

| Field | Data type | description | 
|-|-|-|
| msg | String | Detailed refresh status |
| status | Integer | Corresponding HTTP status code |

**Response example**
```json=
// Success
{
    "status": 200,
    "msg": "Create New SA, DM Name: <dm_name>"
}
// No NA detected
{
    "status": 400,
    "msg": "No NA detected, please create Join point in Project <sa_name>"
}
// Failed at registering AG-SA
{
    "status": 500,
    "msg": "Internal Server Error"
}
```

---

#### *[POST] /sa/create_sa*
**Description**
Creates an empty Field, further procedures will be executed after the user sets up NAs in the IoTtalk GUI and press "Refresh" button.

**Parameters**
| Name | Data type | Description |
|-|-|-|
| cb_id | Integer | The ID of the ControlBoard to create Field in, passed through request body |
| sa_name | String | The Field's name to create IoTtalk Project, passed through request body |

**Request Example**
```json=
{
    "cb_id": 5,
    "sa_name": "Demo_Field"
}
```

**Response**

| Field | Data type | description | 
|-|-|-|
| msg | String | Detailed execution status |
| status | Integer | Corresponding HTTP status code |

**Response example**
```json=
// Success
{
    "status": 200,
    "msg": "Create SA succeeded"
}
// Specified ControlBoard doesn't exist or A project with the same name as <sa_name> already exists
{
    "status": 400,
    "msg": "Create SA failed at creating project, project with the same name already exists."
}
// Failed at creating Device-object
{
    "status": 500,
    "msg": "Internal Server Error"
}
```

---

#### *[POST] /sa/delete_sa*
**Description**
Delete the specified Field and all UserRules related to the sensors/actuators contained in this Field.

**Parameters**
| Name | Data type | Description |
|-|-|-|
| sa_id | Integer | The ID of the Field to delete, passed through request body |

**Request Example**
```json=
{
    "sa_id": 5,
}
```

**Response**

| Field | Data type | description | 
|-|-|-|
| msg | String | Detailed execution status |
| status | Integer | Corresponding HTTP status code |

**Response example**
```json=
// Success
{
    "status": 200,
    "msg": "Delete SA succeeded"
}
// Specified ControlBoard is not running
{
    "status": 400,
    "msg": "Create SA failed at creating project, project with the same name already exists."
}
// AG-related error occurs
{
    "status": 500,
    "msg": "Internal Server Error"
}
```

---

#### *[GET] /sa/get_sa/<cb_id>*

**Description**
Get Field infos of the specified ControlBoard. Called when rendering available Fields to the user.

**Parameters**
| Name | Data type | Description |
|-|-|-|
| cb_id | Integer | The ID of the Field to delete, passed through url |

**Request Example**
```json=
{
    "cb_id": 5,
}
```

**Response**

| Field | Data type | description | 
|-|-|-|
| available_sa | List of Jsons | Fields contained in this ControlBoard |
| status | Integer | Corresponding HTTP status code |

##### The following table explains the fields of each element in *available_sa*
| Field | Data type | description | 
|-|-|-|
| text | String | Name of this Field |
| value | Integer | Unique ID of this Field |
| pin | Boolean | Whether this Field in pinned |

**Response example**
```json=
// Success
{
    "status": 200,
    "available_sa": [
        {
            "text": "Field1",
            "value": 1,
            "pin": false
        },
        {
            "text": "Field2",
            "value": 2,
            "pin": true
        }
    ]
}
// User do not have the proper privilege level
{
    "status": 403,
    "available_sa": "Not a superuser!"
}
```

---

### **Subsystem Related**

#### *[GET] /subsystem/get_accessible_proj/<user_name>*

**Descrpiption**
Returns ControlBoards that are granted to be controlled by user given *user_name*.

**Parameters**
| Name | Data type | Description |
|-|-|-|
| user_name | String | The account of requester, passed through url |

**Request Example**
```json=
{
    "user_name": "pcs54784@nctu.edu.tw"
}
```

**Response**

| Field | Data type | description | 
|-|-|-|
| proj_list | List of Integers | Unique ID of ControlBoards this user can access |
| status | Integer | Corresponding HTTP status code |

**Response example**
```json=
// Success
{
    "status": 200,
    "proj_list": [1, 2, 3, 7, 8, 10]
}
```

---

#### *[POST] /subsystem/set_pinned_field*
**Description**
Set Fields to be pinned in the ControlBoard given `cb_id` and `sa_id` and set all other Fields to un-pinned.

**Parameters**
| Name | Data type | Description |
|-|-|-|
| cb_id | Integer | The ID of the ControlBoard, passed through request body |
| to_pinned | List of Intgers | The ID of Fields to be pinned, passed through request body |

**Request Example**
```json=
{
    "cb_id": 5,
    "to_pinned": [1, 4, 7, 10]
}
```

**Response**

| Field | Data type | description | 
|-|-|-|
| msg | String | Detailed execution status |
| status | Integer | Corresponding HTTP status code |

**Response example**
```json=
// Success
{
    "status": 200,
    "msg": "okay"
}
// Field not contained in specifed ControlBoard detected
{
    "status": 400,
    "msg": "Unrelated SA involved, abort request"
}
```

---

#### *[PUT] /subsystem/cb_icon/<cb_id>*
**Description**
Change specified ControlBoard's icon given `cb_id` and `file` from user.
Modify `Config.ini` to accept different file extensions.

**Parameters**
| Name | Data type | Description |
|-|-|-|
| cb_id | Integer | The ID of the ControlBoard, passed through request body |
| file | JavaScript file | Icon provided by user,passed through request body |

**Request Example**
```json=
{
    "cb_id": 5,
    "file": JS File
}
```

**Response**

| Field | Data type | description | 
|-|-|-|
| msg | String | Detailed execution status |
| status | Integer | Corresponding HTTP status code |

**Response example**
```json=
// Success
{
    "status": 200,
    "msg": "Icon change finished"
}
// Icon's extension not supported
{
    "status": 400,
    "msg": "Non-supported icon format"
}
// User is not a SuperUser
{
    "status": 403,
    "msg": "Not a superuser!"
}
```

---

#### *[POST] /subsystem/create_cb*
**Description**
Creates a Empty ControlBoard.

**Parameters**
| Name | Data type | Description |
|-|-|-|
| text | String | The name of the ControlBoard, passed through request body |

**Request Example**
```json=
{
    "text": "demo-cb",
}
```

**Response**

| Field | Data type | description | 
|-|-|-|
| msg | String | Detailed execution status |
| status | Integer | Corresponding HTTP status code |

**Response example**
```json=
// Success
{
    "status": 200,
    "msg": "Success"
}
// User doesnot exists.
{
    "status": 400,
    "msg": "Non-existed User!"
}
```

---

#### *[POST] /subsystem/delete_cb*
**Description**
Delete the specified ControlBoard and corresponding Fields / UserRules with  cb_id.

**Parameters**
| Name | Data type | Description |
|-|-|-|
| cb_id | Integer | The unique ID of the ControlBoard, passed through request body |

**Request Example**
```json=
{
    "text": "demo-cb",
}
```

**Response**

| Field | Data type | description | 
|-|-|-|
| msg | String | Detailed execution status |
| status | Integer | Corresponding HTTP status code |

**Response example**
```json=
// Success
{
    "status": 200,
    "msg": "Specified ControlBoard and subsequent Fields deleted."
}
// Permission denied.
{
    "status": 403,
    "msg": "Not a superuser!"
}
```

---

#### *[GET] /subsystem/get_cb/<usr_account>*
**Description**
Returns all accessible ControlBoards of the specified user given user account

**Parameters**
| Name | Data type | Description |
|-|-|-|
| usr_account | String | Account of the requester user, passed through url |

**Request Example**
```json=
{
    "usr_account": "pcs54784@nctu.edu.tw",
}
```

**Response**

| Field | Data type | description | 
|-|-|-|
| accessible_cb | A Json with two fields | The requester's accessible ControlBoards and ControlBoards shared to this user |
| status | Integer | Corresponding HTTP status code |

**Response example**
```json=
// Success
{
    "status": 200,
    "accessible_cb": {
        "accessibleProjects": [1, 3, 5, 6, 7], // ID of ControlBoards this user can access.
        "optionProjects": [
            {
                "icon": "./default_icon.svg", // Icon path of this CB
                "text": "CB1", // Name of this CB
                "value": "2" // ID of this CB
            }
        ]
    }
}
// No such User
{
    "status": 401,
    "msg": "No such user"
}
// Permission denied.
{
    "status": 403,
    "msg": "Permission denied"
}
```

---

### Account Releted [Need to be finished after AAA is done]

#### *[GET] /account/get_accounts*
**Description**
Returns all users, the logined user must be privileged to call this entry.

**Parameters**
None

**Response**

| Field | Data type | description | 
|-|-|-|
| users | A List of Jsons | All user's basic information |
| status | Integer | Corresponding HTTP status code |

**Response example**
```json=
// Success
{
    "status": 200,
    "users": [
        {
            "superuser": 2,
            "username": "liny@nctu.edu.tw"
        },
        {
            "superuser": 1,
            "username": "ksoy@nctu.edu.tw"
        },
        {
            "superuser": 0,
            "username": "pcs54784@nctu.edu.tw"
        }
    ]
}
// No such User
{
    "status": 401,
    "msg": "No such user"
}
// Permission denied.
{
    "status": 403,
    "msg": "Permission denied"
}
```



#### *[POST] /account/adjust_privilege/<usr_name>*
**Description**
Adjust user privilege and his/her accessible ControlBoards

**Parameters**
| Name | Data type | Description |
|-|-|-|
| usr_name | String | Account of the specified user, passed through url |
| usr_profile | Json with two fields | the content to adjust |

##### The following table explains what are the meaning of the two fields in *usr_profile*
| Name | Data type | Description |
|-|-|-|
| privilege | Integer | Ranging from 0~2, indicating user/superuser/admin to be applied to this user individually. |
| accessible_cb | List of Integers | Unique ID of ControlBoards this user is granted to access. |


**Request Example**
```json=
{
    "privilege": 1,
    "accessible_cb": [1, 3, 5, 6, 7]
}
```

**Response**

| Field | Data type | description | 
|-|-|-|
| msg | String | Detailed execution status |
| status | Integer | Corresponding HTTP status code |

**Response example**
```json=
// Success
{
    "status": 200,
    "msg": "setup done"
}
// No such User
{
    "status": 401,
    "msg": "No such user"
}
// Permission denied.
{
    "status": 403,
    "msg": "Permission denied"
}
```

---
