Vue.config.devtools = true;
var app = new Vue({
  el: '#app',
  delimiters: ["<%", "%>"],
  data: {
    comparisons: [
      {value: null, text: ""},
      {value: "smaller", html: "&lt;"},
      {value: "bigger", html:"&gt;"}
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
      "superuser": 1,
      "username": "luk1684tw"
    },
    projects: [
      {icon: "../static/imgs/landscape.svg", name: "Hello World"},
      {icon: "../static/imgs/landscape.svg", name: "test_1"},
      {icon: "../static/imgs/landscape.svg", name: "test_2"},
      {icon: "../static/imgs/landscape.svg", name: "test_3"},
      {icon: "../static/imgs/landscape.svg", name: "test_4"},
      {icon: "../static/imgs/landscape.svg", name: "test_5"},
      {icon: "../static/imgs/landscape.svg", name: "test_6"},
      {icon: "../static/imgs/landscape.svg", name: "test_7"}
    ],
    pinnedFields: [
      "Field111111111111111111111111111", "Field2", "Field3", "Field4", "Field5"  
    ],
    fields: [
      "Field111111111111111111111111111", "Field2", "Field3", "Field4", "Field5", "Field6",
      "Field7", "Field8", "Field9", "Field10", "Field11", "Field12", 
    ],
    currentField: 0,
    settings: [
      {
        actuator: "Bulb",
        sensors: ["Luminance", "sensor1", "sensor2", "sensor3"],
        mode: "Sensor",
        value: 100,
        dirty: false,
        status: true,
        content: {
          "open_sensor": "bigger",
          "close_sensor": null,
          "open_timer": [0, 0, 0],
          "close_timer": [0, 0, 0],
          "open_sensorVal": 0,
          "close_sensorVal": 0,
          "weekdays": [7],
        }
      },
      {
        actuator: "Actuator2",
        sensors: ["Humidity", "sensor4", "sensor5", "sensor6"],
        mode: "Sensor",
        value: 200,
        dirty: false,
        status: false,
        content: {
          "open_sensor": "bigger",
          "close_sensor": null,
          "open_timer": [0, 0, 0],
          "close_timer": [0, 0, 0],
          "open_sensorVal": 0,
          "close_sensorVal": 0,
          "weekdays": [7],
        }
      },
      {
        actuator: "Actuator3",
        sensors: ["Test", "sensor7", "sensor8", "sensor9"],
        mode: "ON",
        value: 300,
        dirty: false,
        status: true,
        content: {
          "open_sensor": null,
          "close_sensor": null,
          "open_timer": [0, 0, 0],
          "close_timer": [0, 0, 0],
          "open_sensorVal": 0,
          "close_sensorVal": 0,
          "weekdays": [7],
        }
      },
      {
        actuator: "Actuator4",
        sensors: ["Test1", "sensor10", "sensor11", "sensor12"],
        mode: "OFF",
        value: 400,
        dirty: false,
        status: true,
        content: {
          "open_sensor": null,
          "close_sensor": null,
          "open_timer": [0, 0, 0],
          "close_timer": [0, 0, 0],
          "open_sensorVal": 0,
          "close_sensorVal": 0,
          "weekdays": [7],
        }
      }
    ]
  }, 
  methods: {
    getDefaultSensorSettings: function() {
      return {
        mode: "OFF",
        value: 0,
        dirty: false,
        status: false,
      };
    },
    createField: function() {
      console.log("create field triggered");
    },
    switchField: function(index) {
      this.currentField = index;
    },
    reqFieldData: function(index) {

    },
    // Select source sensor value handler
    onSelectSensor: function(sensorIndex, settingIndex) {
      var temp = this.settings[settingIndex]['sensors'][0];
      this.settings[settingIndex]['sensors'].$set(0, this.settings[settingIndex]['sensors'][sensorIndex]);
      this.settings[settingIndex]['sensors'].$set(sensorIndex, temp);
      console.log(this.settings[settingIndex]['sensors']);
      return;
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
      if (content==="open") {
        this.settings[settingIndex].content.open_sensor = val;
      } else {
        this.settings[settingIndex].content.close_sensor = val;
      }
    },
    // Time select handler
    onSelectTime: function()
  }

})

