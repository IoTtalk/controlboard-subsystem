Vue.config.devtools = true;
var app = new Vue({
  el: '#app',
  delimiters: ["<%", "%>"],
  data: {
    manageMode: false,  // Switch bwtween CB page & manage page
    managePage: false, // Used to switch active state between User/CB management
    privilege: privilege,  // Whether current user is a superuser.
    newCBIcon: null,
    refreshWorker: -1,  // Timer ID for periodically calling current_data
    newCB: {
      text: "",
      shared: false
    },
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
      {value: 1, text: "Super User"},
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
  computed: {
    accessibleProjectObjects: function() {
      toAccess = [];
      for (projectIdx in this.projects.accessibleProjects) {
        toAccess.push(this.projects.optionProjects[projectIdx])
      }
      return toAccess;
    },
    maxPinnedFields: function() {
      console.log(window.outerWidth);
      return Math.floor(window.outerWidth / 80) - 1;
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
    /* API data getter Methods, including CB, SA, Rule, Status, Users, 
    *  Reachable Projects
    */
    getAvailableCBs: function(account) {
      return new Promise(function (resolve, reject) {
        if (account === undefined) {
          account = "self";
        }
        axios
          .get("/subsystem/get_cb/" + account)
          .then(function(res) {
            console.log(res);
            resolve(res.data);
          })
          .catch(function(err) {
            console.log(err);
            reject();
          });
      });
    },
    getAvailableSAs: function(projectID) {
      return new Promise(function (resolve, reject) {
        axios
          .get("/subsystem/get_sa/" + projectID.toString())
          .then(function(res) {
            console.log(res);
            resolve(res.data);
          })
          .catch(function(err) {
            console.log(err);
            reject();
          });
      });
    },
    getSARules: function(fieldID) {
      return new Promise(function (resolve, reject) {
        axios
          .get("/sa/" + fieldID.toString() + "/rules")
          .then( (rules) => {
            console.log(rules);
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
            console.log(status);
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
            console.log(res);
            resolve(res.data);
          })
          .catch( (err) => {
            console.log(err);
            reject(err);
          })
      })
    },
    getAccessibleProjects: function(userName) {
      return new Promise(function (resolve, reject) {
        axios
          .get("/subsystem/get_accessible_proj/" + userName)
          .then( (res) => {
            console.log(res);
            resolve(res.data);
          })
          .catch( (err) => {
            console.log(err);
            reject(err);
          })
      })
    },
    /* Refresh routine procedures, Start from CB, SA, Rule, Status */
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
      pinnedFieldObjects = [];
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
        setting["dirty"] = false;
        setting["time"] = status[setting.ruleID]["time"];
        setting["prevTrigger"] = status[setting.ruleID]["prev_trigger"];
        setting["value"] = status[setting.ruleID]["value"];
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
    },
    onSwitchField: function(fieldID) {
      this.currentField = fieldID;
      this.refreshRuleWorker();
      return;
    },
    onSelectProject: function(selected) {
      this.currentProject = selected;
      this.refreshSAWorker()
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
            console.log("Respond of creating CB", res);
            this.refreshCBWorker();
          })
          .catch(function(error) {
            console.log(error)
          });
      }
      this.newCB = {
        text: "",
        shared: false
      };
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
    *  including create / delete / refresh / confirm / reset
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
            window.clearInterval(this.refreshWorker);
            this.refreshSAWorker();
            this.refreshWorker = setInterval(this.refreshStatusWorker, 1000);
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
    onSAReset: function() {

    },
    onSAConfirm: function(ruleIDs) {
      console.log(ruleIDs);
    },
    onRefreshSA: function() {
      axios
        .get("/subsystem/refresh_sa/" + this.currentField.toString())
        .then( (res)=> {
          console.log(res);
          this.refreshRuleWorker();
        })
        .catch( (err) => {
          console.log(err);
        })
        return;
    },
    /* Rule related procedures 
    *  including selecting mode / which sensor to use /  comparison method / Timing
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
      if (nextMode === undefined || settingIndex === undefined) return;
      switch (nextMode) {
        case 0: // Manual mode
          this.$set(this.settings[settingIndex], "dirty", true);
          if (this.settings[settingIndex].mode==="ON") {
            this.$set(this.settings[settingIndex], "mode", "OFF");
          } else {
            this.$set(this.settings[settingIndex], "mode", "ON");
          }
          break;
        case 1: // Sensor mode
          if (this.settings[settingIndex].mode!=="Sensor") {
            this.$set(this.settings[settingIndex], "dirty", true);
            this.$set(this.settings[settingIndex], "mode", "Sensor");
          }
          break;
        case 2: // Timer mode
          if (this.settings[settingIndex].mode!=="Timer") {
            this.$set(this.settings[settingIndex], "dirty", true);
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
    /* Managing page related procedures 
    *  including user privilege / CB Icon / Accessible CB(Project)
    */
    lvlToText: function(userLvl) {
      if (userLvl === 2) {
        return "Admin";
      } else if (userLvl === 1) {
        return "Super User";
      } else {
        return "User";
      }
    },
    onSelectUserLvl: function(event, userIndex) {
      console.log(event, this.users[userIndex]);
      return;
    },
    onUserUpdate: function(index, action) {
      console.log(index, action);
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
