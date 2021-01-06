Vue.config.devtools = true;
var app = new Vue({
  el: '#app',
  delimiters: ["<%", "%>"],
  data: {
    manageMode: false,  // Switch bwtween CB page & manage page
    managePage: false, // Used to switch active state between User/CB management
    privilege: privilege,  // Whether current user is a superuser.
    newCBIcon: null,
    statusTrackWorker: -1,  // Timer ID for periodically calling current_data
    width: -1,
    newCB: "",
    newSA: {
      text: "",
      pinned: false
    },
    comparisons: [
      {value: "notset", text: ""},
      {value: "smaller", html: "&lt;"},
      {value: "bigger", html:"&gt;"}
    ],
    userlvls: [
      {value: 0, text: "User"},
      {value: 1, text: "Superuser"},
      {value: 2, text: "Admin"}
    ],
    weekdays: [
      {value: 0, text: "Mon"},
      {value: 1, text: "Tue"},
      {value: 2, text: "Wen"},
      {value: 3, text: "Thu"},
      {value: 4, text: "Fri"},
      {value: 5, text: "Sat"},
      {value: 6, text: "Sun"},
      {value: 7, text: "All"}
    ],
    hours: [
      0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
      12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23
    ],
    minutes: [
      0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
      15, 16, 17, 18, 19, 20 ,21 ,22 ,23 ,24, 25, 26, 27, 28, 29,
      30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
      45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59
    ],
    seconds: [
      0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
      15, 16, 17, 18, 19, 20 ,21 ,22 ,23 ,24, 25, 26, 27, 28, 29,
      30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44,
      45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59
    ],
    users: [],
    projects: { // All Shared projects of CB Subsystem + User's projects
      accessibleProjects: [], // CB_ID of CBs this user can control
      optionProjects: []  // All CBs this user can see.
    },
    accessibleProjects: [],  // Empty list to save accessible Project(CB) changes in manage page.
    fields: {
      pinnedFields: [],
      optionFields: []
    },
    pinnedFields: [],  // Empty list to save pinned Field(SA) changes.
    currentField: 0,  // Field refers to SA in a specific CB.
    currentProject: 0,  // Project refers to CB.
    backupSettings: [],
    settings: []
  },
  created: function() {
    // Procedures to correctly render data:
    // get CBs -> get SAs -> get Rules -> get Status
    this.refreshCBWorker();
    this.statusTrackWorker = setInterval(this.refreshStatusWorker, 1000);
    this.width = window.innerWidth;
    window.addEventListener("resize", this.onWindowResize);
    if (this.privilege) {
      console.log("get user");
      this.getAllUsers()
        .then( (users) => {
          this.users = users;
        })
        .catch( (err) => {
          console.log(err);
        });
    }
    return;
  },
  destoryed: function() {
    window.removeEventListener("resize", this.onWindowResize);
  },
  computed: {
    accessibleProjectObjects: function() {
      toAccess = [];
      this.projects.optionProjects.forEach( project => {
        if (this.projects.accessibleProjects.includes(project.value)) {
          toAccess.push(project);
        }
      });
      return toAccess;
    },
    maxPinnedFields: function() {
      return Math.floor(this.width / 80) - 1;
    },
    currentFieldName: function() {
      var name = "";
      this.fields.optionFields.forEach(field => {
        if (field.value === this.currentField) {
          name = field.text;
        }
      });
      return name;
    },
    unPinnedFields: function() {
      var fields = [];
      this.fields.optionFields.forEach(field => {
        if (!this.fields.pinnedFields.includes(field)) {
          fields.push(field);
        }
      })
      console.log(fields);
      return fields;
    }
  },
  methods: {
    /* API data getter Methods, including CB, SA, Rule, Status, User, 
    *  Reachable Project
    */
    getAvailableCBs: function(account) {
      return new Promise(function (resolve, reject) {
        if (account === undefined) {
          account = "self";
        }
        axios
          .get("/subsystem/get_cb/" + account)
          .then(function(res) {
            res.data.optionProjects.sort((a, b) => b.value - a. value);
            resolve(res.data);
          })
          .catch(function(err) {
            reject();
          });
      });
    },
    getAvailableSAs: function(projectID) {
      return new Promise(function (resolve, reject) {
        axios
          .get("/subsystem/get_sa/" + projectID.toString())
          .then(function(res) {
            resolve(res.data);
          })
          .catch(function(err) {
            reject();
          });
      });
    },
    getSARules: function(fieldID) {
      return new Promise(function (resolve, reject) {
        axios
          .get("/sa/" + fieldID.toString() + "/rules")
          .then( (rules) => {
            resolve(rules.data);
          })
          .catch( (err) => {
            reject(err);
          });
      });
    },
    getRuleStatus: function(fieldID) {
      return new Promise(function (resolve, reject) {
        axios
          .get("/sa/" + fieldID.toString() + "/current_data")
          .then( (status) => {
            resolve(status.data);
          })
          .catch( (err) => {
            reject(err);
          });
      });
    },
    getAllUsers: function() {
      return new Promise(function (resolve, reject) {
        axios
          .get("/account/get_accounts")
          .then( (res) => {
            res.data.sort((a, b) => b.superuser - a.superuser);
            resolve(res.data);
          })
          .catch( (err) => {
            reject(err);
          })
      })
    },
    getAccessibleProjects: function(userName) {
      return new Promise(function (resolve, reject) {
        axios
          .get("/subsystem/get_accessible_proj/" + userName)
          .then( (res) => {
            resolve(res.data);
          })
          .catch( (err) => {
            reject(err);
          })
      })
    },
    /* Refresh routine procedures, including CB, SA, Rule, Status */
    refreshCBWorker: function() {
      this.getAvailableCBs()
        .then( (projects) => {
          this.projects = projects;
          if (projects.accessibleProjects.length)
            this.currentProject = projects.accessibleProjects[0];
          else
            this.currentProject = 0;
          this.refreshSAWorker();
        })
        .catch( (err) => {
          console.log(err);
        })
    },
    refreshSAWorker: function() {
      this.getAvailableSAs(this.currentProject)
        .then( (fields) => {
          this.setupFields(fields);
          this.refreshRuleWorker();
        })
        .catch( (err) => {
          console.log(err);
        })
    },
    refreshRuleWorker: function() {
      this.getSARules(this.currentField)
        .then( (rules) => {
          this.backupSettings = JSON.parse(JSON.stringify(rules));
          this.settings = rules;
          this.refreshStatusWorker();
        })
        .catch( (err) => {
          console.log(err);
        })
    },
    refreshStatusWorker: function() {
      if (this.settings.length) {
        this.getRuleStatus(this.currentField)
          .then( (status) => {
            this.setupRuleStatus(status);
          })
          .catch( (err) => {
            console.log(err);
          });
      }
      return;
    },
    /* API data parser for SA(Field) and Status*/
    setupFields: function(fields) {
      fields.sort((a, b) => b.value - a.value);
      pinnedFieldObjects = [];
      this.pinnedFields = [];
      fields.forEach(element => {
        if (element.pin) {
          pinnedFieldObjects.push(element);
          this.pinnedFields.push(element.value)
        }
      });
      this.fields = {
        "pinnedFields": pinnedFieldObjects,
        "optionFields": fields
      };
      if (fields.length) {
        if (pinnedFieldObjects.length) {
          this.currentField = pinnedFieldObjects[0].value;
        } else {
          this.currentField = fields[0].value;
        }
      } else {
        this.currentField = 0;
      }
      console.log(this.fields);
    },
    setupRuleStatus: function(status) {
      this.settings.forEach( setting => {
        setting["time"] = status[setting.ruleID]["time"];
        setting["prevTrigger"] = status[setting.ruleID]["prev_trigger"];
        setting["value"] = status[setting.ruleID]["value"].toFixed(2);
        setting["status"] = status[setting.ruleID]["status"] === "RED"? true: false;
      });
      return;
    },
    /* System related handler, 
    *  including manage page switching handlers and CB(Project)/SA(Field) selecting.
    */
    onSwitchManage: function() {
      this.manageMode = !this.manageMode;
      return;
    },
    onSwitchManagePage: function() {
      this.managePage = !this.managePage;
      return;
    },
    onSwitchField: function(fieldID) {
      window.clearInterval(this.statusTrackWorker);
      this.currentField = fieldID;
      this.refreshRuleWorker();
      this.statusTrackWorker = setInterval(this.refreshStatusWorker, 1000);
      return;
    },
    onSelectProject: function(selected) {
      window.clearInterval(this.statusTrackWorker);
      this.currentProject = selected;
      this.manageMode = false;
      this.managePage = false;
      this.refreshSAWorker()
      this.statusTrackWorker = setInterval(this.refreshStatusWorker, 1000);
      return;
    },
    /* CB(Project) related procedures 
    *  including create / delete / pin field
    */
    onCBCreate: function(action) {
      if (1 === action) {
        axios
          .post("/subsystem/create_cb", this.newCB)
          .then( (res) => {
            console.log("Response of creating CB", res);
            this.refreshCBWorker();
          })
          .catch(function(error) {
            console.log(error)
          });
      }
      this.newCB = "";
      return;
    },
    onCBDelete: function(cbID, action) {
      if (1 === action) {
        axios
        .post("/subsystem/delete_cb", cbID)
        .then( (res) => {
          console.log(res);
          this.refreshCBWorker();
        })
        .catch(function(error) {
          console.log(error);
        });
      }
    },
    onPinFields: function(action) {
      if (action && this.currentProject) {
        data = {
          "cb_id": this.currentProject,
          "to_pinned": this.pinnedFields
        };
        axios.post("/subsystem/set_pinned_field", data)
          .then( (res) => {
            console.log(res);
            this.getAvailableSAs(this.currentProject)
              .then( (fields) => {
                this.setupFields(fields);
              })
              .catch( (err) => {
                console.log(err);
              })
          })
          .catch( (err) => {
            console.log(err);
          })
      }
    },
    /* SA(Field) related procedures 
    *  including create / delete / refresh / confirm / reset / undo / Resize pinned SA
    */
    onSACreate: function(action) {
      if (1 === action) {
        data = {
          "sa": this.newSA,
          "cb_id": this.currentProject
        }
        axios
          .post("/subsystem/create_sa", data)
          .then( (res) => {
            console.log(res);
            this.refreshSAWorker();
            
          })
          .catch( (err) => {
            alert(err);
          })
      }
      this.newSA = {
        text: "",
        pinned: false
      };
      return;
    },
    onSADelete: function(action) {
      if (1 === action) {
        axios
          .post("subsystem/delete_sa", this.currentField)
          .then( (res) => {
            console.log(res);
            this.refreshSAWorker();
          })
          .catch( (err) => {
            console.log(err);
          })
      }
    },
    onSAConfirm: function() {
      ruleIDs = [];
      this.settings.forEach((setting, index) => {
        if (setting["dirty"]) {
          ruleIDs.push(index);
        }
      });
      console.log(ruleIDs);
      this.onSettingSaveChange(ruleIDs);
      return;
    },
    onSAReset: function() {
      ruleIDs = [];
      this.settings.forEach((setting, index) => {
        ruleIDs.push(index);
        setting["mode"] = "OFF";
      });
      console.log(ruleIDs);
      this.onSettingSaveChange(ruleIDs);
      return;
    },
    onSettingSaveChange: function(ruleIdx) {
      console.log(ruleIdx);
      toChange = [];
      ruleIdx.forEach( idx => {
        var setting = this.settings[idx];
        setting["dirty"] = false;
        toChange.push({
          "actuator_alias": setting["actuator"],
          "mode": setting["mode"],
          "sensor_index": setting["selectedSensor"],
          "threshold_open": setting["content"]["openSensorVal"],
          "threshold_close": setting["content"]["closeSensorVal"],
          "comparison_open": setting["content"]["openSensor"],
          "comparison_close": setting["content"]["closeSensor"],
          "time_open": setting["content"]["openTimer"],
          "time_close": setting["content"]["closeTimer"],
          "weekday": setting["content"]["weekdays"],
          "duty_pos": setting["content"]["dutyPos"],
          "duty_neg": setting["content"]["dutyNeg"]
        });
      });
      console.log(toChange);

      axios.post("/sa/" + this.currentField.toString() + "/new_rules", toChange)
        .then( (msg) => {
          window.clearInterval(this.statusTrackWorker);
          console.log(msg);
          this.refreshRuleWorker();
          this.statusTrackWorker = setInterval(this.refreshStatusWorker, 1000);
        })
        .catch( (err) => {
          console.log(err);
        })
      return;
    },
    onRefreshSA: function() {
      window.clearInterval(this.statusTrackWorker);
      axios
        .get("/subsystem/refresh_sa/" + this.currentField.toString())
        .then( (res)=> {
          console.log(res);
          this.refreshRuleWorker();
          this.statusTrackWorker = setInterval(this.refreshStatusWorker, 1000);
        })
        .catch( (err) => {
          console.log(err);
        })
        return;
    },
    onSettingUndoChange: function(settingIndex) {
      this.$set(this.settings, settingIndex, 
        JSON.parse(JSON.stringify(this.backupSettings[settingIndex])));
      this.settings[settingIndex]["dirty"] = false;
      console.log(this.settings[settingIndex]);
      return;
    },
    onWindowResize: function() {
      this.width = window.innerWidth * 0.98;
      return;
    },
    /* Rule related procedures 
    *  including selecting mode / which sensor to use /  comparison method / Timing / Calculate Duty Cycle Stage.
    */
    onSelectSensor: function(selected, ruleID) {
      console.log(selected, ruleID);
      this.settings.forEach( (setting) => {
        if (setting.ruleID === ruleID) {
          setting.dirty = true;
          setting.selectedSensor = selected;
          return;
        }
      })
    },
    onSelectMode: function(nextMode, settingIndex) {
      console.log(nextMode);
      this.$set(this.settings[settingIndex], "dirty", true);
      if (nextMode === undefined || settingIndex === undefined) return;
      switch (nextMode) {
        case 0: // OFF
          if (this.settings[settingIndex].mode!=="OFF") {
            this.$set(this.settings[settingIndex], "mode", "OFF");
          }
          break;
        case 1:
          if (this.settings[settingIndex].mode!=="ON") {
            this.$set(this.settings[settingIndex], "mode", "ON");
          }
          break;
        case 2: // Sensor mode
          if (this.settings[settingIndex].mode!=="Sensor") {
            this.$set(this.settings[settingIndex], "mode", "Sensor");
          }
          break;
        case 3: // Timer mode
          if (this.settings[settingIndex].mode!=="Timer") {
            this.$set(this.settings[settingIndex], "mode", "Timer");
          }
          break;
        default:
          console.log("Unsupported Input mode");
          break;
      }
      console.log(this.settings[settingIndex]);
      return;
    },
    onSelectCompare: function(val, settingIndex, content) {
      console.log(val, settingIndex, content);
      this.settings[settingIndex].dirty = true;
      if (content==="open") {
        this.settings[settingIndex].content.openSensor = val;
      } else {
        this.settings[settingIndex].content.closeSensor = val;
      }
    },
    onSelectTime: function(val, settingIndex, content) {
      console.log(val, settingIndex, content);
      this.settings[settingIndex].dirty = true;
      if (content < 3) {
        this.settings[settingIndex].content.openTimer[content] = val;
      } else {
        this.settings[settingIndex].content.closeTimer[content - 3] = val;
      }
    },
    onSelectWeekdays: function(event, settingIndex) {
      console.log(event, settingIndex);
      console.log(this.settings[settingIndex].content.weekdays);
      this.settings[settingIndex].dirty = true;
      inputSelectAll = (event.indexOf(7) >= 0);
      dataSelectAll = (this.settings[settingIndex].content.weekdays.indexOf(7) >= 0);
      tempArr = [];
      if (dataSelectAll && event.length <= 7) {
        event.forEach(element => {
          if (element !== 7) {
            tempArr.push(element);
          }
        });
      } else {
        if (inputSelectAll) {
          for (i = 0; i < 8; i++) {
            tempArr.push(i);
          }
        } else {
          event.forEach(element => {
              tempArr.push(element);
          });
        }
      }
      this.$set(this.settings[settingIndex].content, "weekdays", tempArr);
      return;
    },
    onJudgeDutyCycle: function(setting) {
      if (setting.prevTrigger === -10000) {
        return "";
      }
      if (setting.status) {
        return "POS";
      } else {
        return "NEG";
      }
    },
    /* Managing page related procedures 
    *  including user privilege / CB Icon / Accessible CB(Project)
    */
    lvlToText: function(userLvl) {
      if (userLvl === 2) {
        return "Admin";
      } else if (userLvl === 1) {
        return "Superuser";
      } else {
        return "User";
      }
    },
    onSelectUserLvl: function(event, userIndex) {
      this.users[userIndex].superuser = event;
      return;
    },
    onUserUpdate: function(index, action) {
      if (1 === action) {
        data = {
          "privilege": this.users[index].superuser,
          "accessible_cb": this.accessibleProjects
        };
        axios.post("/account/adjust_privilege/" + this.users[index].username, data)
          .then( (res) => {
            console.log(res);
            this.getAllUsers()
              .then( (usrs) => {
                this.users = usrs;
              })
              .catch( (err) => {
                console.log(err);
              });
            this.refreshCBWorker();
          })
          .catch( (err) => {
            console.log(err);
          });
      }
    },
    onIconUpload: function(cbID, action) {
      console.log(cbID, action);
      if (1 === action) {
        let formData = new FormData();
        formData.append("file", this.newCBIcon);
        formData.append("cb_id", cbID);
        axios
          .put("/subsystem/cb_icon/" + cbID.toString(), formData, {
            headers: {
              "Content-Type": "multipart/form-data"
            }
          })
          .then( (res) => {
            console.log(res);
            this.refreshCBWorker();
          })
          .catch(function(error) {
            console.log(error);
          });
      }
      this.newCBIcon = null;
    },
    onAccessibleCB: function(userName) {
      this.getAccessibleProjects(userName)
        .then( (projs) => {
          this.accessibleProjects = projs;
        })
        .catch( (err) => {
          console.log(err);
        })
    }
  }
})
