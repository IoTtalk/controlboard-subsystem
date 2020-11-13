var app = new Vue({
  el: '#app',
  delimiters: ["<%", "%>"],
  data: {
    comparisons: [
      {value: null, text: ""},
      {value: "bigger", html: "&lt;"},
      {value: "smaller", html:"&gt;"}
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
        mode: "Timer",
        value: 100
      },
      {
        actuator: "Actuator2",
        sensors: ["Humidity", "sensor4", "sensor5", "sensor6"],
        mode: "Sensor",
        value: 200
      },
      {
        actuator: "Actuator3",
        sensors: ["Test", "sensor7", "sensor8", "sensor9"],
        mode: "ON",
        value: 300
      },
      {
        actuator: "Actuator4",
        sensors: ["Test1", "sensor10", "sensor11", "sensor12"],
        mode: "OFF",
        value: 400
      }
    ]
  }, 
  methods: {
    createField: function() {
      console.log("create field triggered");
    },

    switchField: function(index) {
      this.currentField = index;
    },

    reqFieldData: function(index) {

    }
  }

})

