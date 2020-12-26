Vue.config.devtools = true;
var app = new Vue({
  el: '#app',
  delimiters: ["<%", "%>"],
  data: {
    manageMode: false,  // Switch bwtween CB page & manage page
    managePage: false, // Used to switch active state between User/CB management
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
    user: {
      current: {
        "superuser": 1,
        "username": "luk1684tw"
      },
      users: [
        {"superuser": 2, "username": "liny@gmail.com"},
        {"superuser": 1, "username": "jyneda@gmail.com"},
        {"superuser": 1, "username": "ksoy@gmail.com"},
        {"superuser": 1, "username": "iblis@gmail.com"},
        {"superuser": 0, "username": "awscloud666@gmail.com"},
      ]
    },
    projects: { // All Shared projects of CB Subsystem + User's projects
      accessibleProjects: [], // Accessible CBs' IDs 
      optionProjects: []
    },
    fields: {
      pinnedFields: [],
      optionFields: []
    },
    currentField: 0,  // Field refers to SA in a specific CB.
    currentProject: 0,  // Project refers to CB.
    backupSettings: [],
    settings: []
  },
  created: function() {
    // Procedures to correctly render data:
    // get CBs -> get SAs -> get Rules -> get Status
    this.getAvailableCBs()
      .then( (projects) => {
        this.projects = projects;
        this.currentProject = projects["accessibleProjects"][0];
        this.getAvailableSAs(projects["accessibleProjects"][0])
          .then( (fields) => {
            this.setupFields(fields);
            this.getSARules(this.currentField)
              .then( (rules) => {
                this.backupSettings = JSON.parse(JSON.stringify(rules));
                this.settings = rules
                if (rules.length) {
                  this.getRuleStatus(this.currentField)
                    .then( (status) => {
                      this.setupRuleStatus(status);
                    })
                    .catch( (err) => {
                      console.log(err);
                    });
                }
                this.refreshWorker = setInterval(this.refreshStatusWorker, 1000);
              })
              .catch( (err) => {
                console.log(err);
              })
          })
          .catch( () => {
            console.log("fetch SAs failed");
          });
      })
      .catch( () => {
        console.log("created catch");
      });
  },
  computed: {
    accessibleProjects: function() {
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
    getAvailableCBs: function() {
      return new Promise(function (resolve, reject) {
        axios
          .get("/subsystem/get_cb")
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
    onRefreshSA: function() {
      axios
        .get("/subsystem/refresh_sa/" + this.currentField.toString())
        .then( (res)=> {
          this.getSARules(this.currentField)
            .then( (rules) => {
              this.backupSettings = JSON.parse(JSON.stringify(rules));
              this.settings = rules;
              if (rules.length) {
                this.getRuleStatus(this.currentField)
                  .then( (status) => {
                    window.clearInterval(this.refreshWorker);
                    this.setupRuleStatus(status);
                    this.refreshWorker = setInterval(this.refreshStatusWorker, 1000);
                  })
                  .catch( (err) => {
                    console.log(err);
                  })
              }
            })
            .catch( (err) => {
              console.log(err);
            });
        })
        .catch( (err) => {
          console.log(err);
        })
        return;
    },
    setupFields: function(fields) {
      pinnedFields = [];
      fields.forEach(element => {
        if (element.pin) {
          pinnedFields.push(element);
        }
      });
      this.fields = {
        "pinnedFields": pinnedFields,
        "optionFields": fields
      };
      if (fields.length) {
        if (pinnedFields.length) {
          this.currentField = pinnedFields[0].value;
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
    onSwitchManage: function() {
      this.manageMode = !this.manageMode;
      return;
    },
    onSwitchManagePage: function() {
      this.managePage = !this.managePage;
    },
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
            this.getAvailableSAs(this.currentProject)
              .then( (fields) => {
                this.setupFields(fields);
                this.getSARules(this.currentField)
                  .then( (rules) => {
                    this.backupSettings = JSON.parse(JSON.stringify(rules));
                    this.settings = rules;
                    if (rules.length) {
                      this.getRuleStatus(this.currentField)
                        .then( (status) => {
                          this.setupRuleStatus(status);
                        })
                        .catch( (err) => {
                          console.log(err);
                        })
                    }
                  })
                .catch( (err) => {
                  console.log(err);
                })  
              })
              .catch( (err) => {
                console.log(err);
              })
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
            this.getAvailableSAs(this.currentProject)
              .then( (fields) => {
                window.clearInterval(this.refreshWorker);
                this.setupFields(fields);
                this.getSARules(this.currentField)
                  .then( (rules) => {
                    this.backupSettings = JSON.parse(JSON.stringify(rules));
                    this.settings = rules;
                    if (rules.length) {
                      this.getRuleStatus(this.currentField)
                        .then ( (status) => {
                          this.setupRuleStatus(status);
                          this.refreshWorker = setInterval(this.refreshStatusWorker, 1000);
                        })
                        .catch( (err) => {
                          console.log(err);
                        })
                    }
                  })
                  .catch( (err) => {
                    console.log(err);
                  })
              })
          })
          .catch
      }
    },
    switchField: function(index) {
      this.currentField = index;
      this.getSARules(this.currentField)
        .then( (rules) => {
          this.backupSettings = JSON.parse(JSON.stringify(rules));
          this.settings = rules;
          if (rules.length) {
            this.getRuleStatus(this.currentField)
              .then( (status) => {
                this.setupRuleStatus(status);
              })
              .catch( (err) => {
                console.log(err);
              })
          }
        })
        .catch( (err) => {
          console.log(err);
        });
    },
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
    // Select trigger mode handler
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
    // Sensor comparision select handler
    onSelectCompare: function(val, settingIndex, content) {
      console.log(val, settingIndex, content);
      this.settings[settingIndex].dirty = true;
      if (content==="open") {
        this.settings[settingIndex].content.openSensor = val;
      } else {
        this.settings[settingIndex].content.closeSensor = val;
      }
    },
    // Time select handler
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
      console.log(event, userIndex);
      return;
    },
    onCBCreate: function(action) {
      if (1 === action) {
        axios
          .post("/subsystem/create_cb", this.newCB)
          .then( (res) => {
            console.log("Respond of creating CB", res);
            this.getAvailableCBs()
              .then( (projects) => {
                this.projects = projects;
                if (projects.accessibleProjects.length)
                  this.currentProject = projects.accessibleProjects[0];
                else
                  this.currentProject = 0;
              })
              .catch( (error) => {
                console.log(error);
              });
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
          this.getAvailableCBs()
          .then( (projects) => {
            this.projects = projects;
          })
          .catch( () => {
            console.log("re-fetch CB failed");
          });
        })
        .catch(function(error) {
          console.log(error);
        });
      }
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
            this.getAvailableCBs()
              .then( (projects) => {
                this.projects = projects;
              })
              .catch( () => {
                console.log("re-fetch CB failed");
              });
          })
          .catch(function(error) {
            console.log(error);
          });
      }
      this.newCBIcon = null;
    },
    onGetAllCB: function() {

    }
  }

})
