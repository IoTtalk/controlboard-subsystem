# ControlBoard Subsystem User Manual
###### tags: `IoT` `Remote Control` 
Cyber objects are the visual representations that map to physical devices existing in the real world. Users can interact with these physical devices through their cyber representations.

A typical example of such usage is to relate one cyber object to another, creating an **Network Application**(NA) that can automatically take user-defined actions as the cyber representaions of these physical devices update.

But as the number of NAs grow, it would cost huge efforts to the management and visualization of those NAs. Besides, it's difficult to set up the custom actions one by one should there be a plenty of NAs needed.

Here we propose **ControlBoard Subsystem**(CB Subsystem), a subsystem of the IoTtalk ecosystem. CB Subsystem provides an user-friendly GUI for users to control and manage their NAs quickly and easily by applying the **ControlBoards**.

A **ControlBoard** is consisted of **Fields**, and is viewed as an **logical Field** that may contain many different types of devices installed in different Fields. 

A **Field** is the basic managing unit in CB Subsystem, representing an IoTtalk project. Users create NAs at the IoTtalk Project GUI, and these just-created NAs will be automatically visualized in the CB Subsystem GUI.

Users can decide how to manage their NAs using Fields at their convenience. For example, users can place cyber objects into the same Fields according to their geographical locations or the functionalities of the mapped physical devices.

With CB Subsystem, users can directly develop or configure their IoT applications quickly in an easy manner through our GUI without any extra coding owing to the deep integration with the IoTtalk ecosystem. 

## Installation

### System Requirements
- `python >= 3.6`
- Two ports for Flask Server and ZMQ Status Collector respectively (default 7789, 7790)
- AG Subsystem with the following packages installed
    - PonyORM
    - pymysql
    - ZMQ
    - `pip install pymysql pony zmq`
- IoTtalk Server compatible with CCM API
- (optional) MySQL server

---

The following commands are based on assuming your OS is Linux.
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
---

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

    # Default Admin account. Must be an AAA-compatible account
    admin = luk1684tw@gmail.com
    
    # Email Notifier Sender. Can be retained
    sender = ControlBoard@iottalk.tw

    # Email Title. Can be retained
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

---

## How to use
There are two main features in ControlBoard Subsystem.
- ControlBoard
- Management system

In the following sections we'll illustrate how to use these two features.

---

### ControlBoard

#### **Step 1. Open the browser**
1. Enter the URL of CB Subsystem, you'll be redirected to AAA login page first
![](https://i.imgur.com/5mdHNwR.png)


2. Login with the admin account filled in *Config.ini*

3. The browser will be redirect to CB GUI automatically
    ![](https://i.imgur.com/5DPxZzC.png)

    *Figure 1. CB GUI when no CB is accessible.*

4. Switch to management page by clicking *System* button(*Figure 1-b*)

---

#### **Step 2. Create an empty ControlBoard**
1. Click the *plus* button(*Figure 2-a*) in management page.

2. Enter the name of this CB in the corresponding modal(*Figure 2-b*)

3. Press the "OK" button
![](https://i.imgur.com/Y6edm3h.png)

*Figure 2. ControlBoard Creation*

---

#### **Step 3. Create a empty Field**
1. Return to GUI by clicking the *System* button(*Figure 1-b*) again

2. Click "New Field" (*Figure 3-a*)

3. Fill the name of this Field in the poped up modal(*Figure 3-b*), note that the name can not be repeated with existed Fields.

4. Click the *pinned* checkbox(*Figure 3-c*)

5. Press the "OK" button
![](https://i.imgur.com/Pd7Xx3b.png)

*Figure 3. Field Creation*

---

#### **Step 4. Configure the IoTtalk project**
1. Go to the IoTtalk Server GUI

2. Choose the project with the same title as the Field created in **Step 3.** The ControlBoard Device Model will be placed in the project in advance 

3. Select the device model objects needed for your application.
    Connect the Sensor's IDF(*Figure 4-a*) to ControlBoard's ODF(*Figure 4-c*), and then connect the **corresponding** IDF(*Figure 4-d*) of ControlBoard to Actuator's ODF(*Figure 4-e*)

    ![](https://i.imgur.com/JOfW5gm.png)

    *Figure 4. Example Configuration for ControlBoard*
    
    Take *Figure 4.* for example, we want to use *Temperature* to control the *switch* of the fan, then the IDF *Temperature*(*Figure 4-b*) and the ODF *Switch*(*Figure 4-f*) must be connect to the same pair of ControlBoard's DF.

4. If a NA has multiple data resource, we need to right click the join circle(*Figure 4-g*) to edit it's join function(*Figure 4-h*) to transfer all resource data through the join circle.

    Example Join function as follows
    ```python=
    def run(args*):
        return args
    ```

---

#### **Step 5. Refresh the Field to visualize the created NAs**
1. After finishing NA configuration, go back to CB GUI and click refresh(*Figure 5-a*)

2. The NAs created will be visualized as below(*Figure 5-b, 5-c*)
![](https://i.imgur.com/RzT0Hid.png)

*Figure 5. NA setup GUI*

3. If there is any modification on the IoTtalk GUI(i.e. alias, NA), just click Refresh again and the GUI will be automatically updated.

4. Once a Field is refreshed, all the users that has access control to this Field will receive a email notifying that someone has refreshed the Field.
![](https://i.imgur.com/d9YTdUD.png)

*Figure 6. Email notifying the Field is refreshed*

---

#### **Step 6. Configure the NAs in CB Subsystem GUI**
*Figure 7.* illustrates what can be configured in an NA to automatically control the devices.


![](https://i.imgur.com/xHrRIIu.png)

*Figure 7. NA setup GUI(cont.)*

- *Sensor Name* (*Figure 7-a*)
    The name of the currently connected sensor. Can be modified via IoTtalk project GUI
    If the mode of this NA is set to *Timer*, shows "Timer" (*Figure 7-h*) instead.
    
    If there are multiple resource sensors, a dropdown will be placed for users to select which to use.

- *Actuator Name* (*Figure 7-d*)
    The name of the connected actuator.

- *Current Sensor Value* (*Figure 7-b, 7-i*)
    Current value received from the cyber representation of the physical sensory device. If the mode of this NA is set to *Timer*, shows current time (*Figure 7-i*) instead.
    
- *Current Status* (*Figure 7-k*)
    Current Status of the actuator, green represents that the actuator is closed, red means the actuator is opened.

- *Trigger Mode* (*Figure 7-c*)
    Mode of this NA. Currently CB Subsystem supports the following modes
    - *Manual Close / Manual Open*： User's manual operation.
    - *Sensor*：Actuator is automatically controlled by the connected sensor.
    - *Timer*：Actuator is automatically controlled by current time.

- *Threshold Setup* (*Figure 7-e, 7-j*)
    Conditions to trigger or close the actuator, can be further divided into Sensor mode (*Figure 7-e*) or Timer mode (*Figure 7-j*) depending on the NA's mode.

    - *Sensor mode*： user can setup two threshold conditions to automatically control the actuator. The actuator will be opened if both open/close threshold conditions are satisfied.
    - *Timer mode*： user can setup two timing on the GUI in "%H%M%S" format, the actuator will be triggered during this period of time and closed otherwise.

- *Working days* (*Figure 7-f*)
    Users can specify weekdays for this NA to work. The NA will close the actuator when the weekday changes to weekdays that it's not allowed to execute.
    
- *Duty Cycle* (*Figure 7-g*)
    Users can specify the duty cycle length when the actuator is triggered. It's useful should the actuator be the type that can't be continuously triggered, i.e. Drips or Fertilizers.
    
Once the configurations of NAs in a Field is changed, all the users that has access control to this Field will receive a email notifying that someone has changed the configurations.
![](https://i.imgur.com/40KWqtd.png)

*Figure 8. Email notifying the configurations is modified*


---

### Management system

The management of ControlBoard Subsystem is consisted of two parts.
- ControlBoard management：CB-related operations
- User privilege management
    - User privilege level management
        - *`User`*：Normal user, cannot access the management system.
        - *`Superuser`*：In charge of CB accessibilities of users.
        - *`Administrator`*：In charge of user privileges.

    - CB accessibility management
        - All users except *`Administrators`* can only control CBs that are accessible to them.
        - An *`Administrator`* can access all CBs created.
        - *`Administrators`* and *`Superusers`* can further authorize other users to access CBs that they can access.

---

In the following sections we'll explain these operations mentioned with step-by-step tutorials and illustrations.

#### ControlBoard Management

All accessible CBs of the logined user will be listed here(*Figure 9-b*)
Users can switch to User privilege management page by click "User" (*Figure 9-a*)

There are 3 operations supported for CB management.
- ControlBoard Creation (*Figure 9-c*)
- ControlBoard Deletion (*Figure 9-d*)
- Custom ControlBoard Icon (*Figure 9-e*)
    
![](https://i.imgur.com/wqnsPW7.png)

*Figure 9. CB Management Overview*

---

##### **ControlBoard Creation**
Refer to **Step 2. Create an empty ControlBoard** of ControlBoard usage.

---

##### **ControlBoard Deletion**
ControlBoard supports cascade-delete, meaning that when you delete a ControlBoard, all the Fields inside will also be destoryed.

1. Login as *`Superuser`* or above.

2. Switch to management page.

3. Find the CB to be deleted, click the corresponding "Delete CB"(*Figure 10-a*) and then click "OK"(*Figure 10-b*)

![](https://i.imgur.com/PnoXrf2.png)

*Figure 10. ControlBoard Deletion*

---

##### **Custom ControlBoard Icon**
CB Subsystem supports custom icon(*Figure 11-a*) of created CBs, the uploaded icons will be saved in the backend, users can check *Config.ini* for supported file extensions.
1. Login as *`Superuser`* or above.

2. Switch to management page.

3. Find the desired CB, and click the corresponding "Icons"(*Figure 11-b*). Click "Browse"(*Figure 11-c*) and select files to upload.

4. The selected file's filename will be displayed in the modal(*Figure 11-d*)
5. Click "OK" and the icon should be replaced with the uploaded image.
![](https://i.imgur.com/zDs7Yor.png)

*Figure 11. CB Icon Setup*

---

#### User Privilege Management

All users and their privilege level will be listed here(*Figure 12-b, 12-c*)
Users can switch to CB management page by click "ControlBoard" (*Figure 12-a*)

![](https://i.imgur.com/cfoHK1n.png)

*Figure 12. User Management Overview*

There are two operations supported for user privilege management
- User privilege adjustment.
- CB accessibility adjustment.

---

##### **User privilege adjustment**
1. Click the account of the target user(*Figure 13-a*)

2. Select the privilege level to assign to this user in the popped-up modal(*Figure 13-b*)

3. Note that users cannot assign privileges higher than that of them.
    For example, a *`Superuser`* cannot assign others to be *`Administrator`*

![](https://i.imgur.com/PXQnTa6.png)

*Figure 13. User Permission Adjustment*

---

##### **CB accessibility adjustment**
1. Click the account of the target user(*Figure 13-a*)

2. Select CBs to be shared to this user in the popped-up modal(*Figure 13-c*) by click the corresponding checkbox of these CBs.

3. To disable the user's access control to a specific CB, just cancel the corresponding checkbox of this CB.
