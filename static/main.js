var app = new Vue({
  el: '#app',
  delimiters: ["<%", "%>"],
  data: {
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
      },
      {
        actuator: "Actuator2",
        sensors: ["Humidity", "sensor4", "sensor5", "sensor6"],
        mode: "Sensor",
      },
      {
        actuator: "Actuator3",
        sensors: ["Test", "sensor7", "sensor8", "sensor9"],
        mode: "ON",
      },
      {
        actuator: "Actuator4",
        sensors: ["Test1", "sensor10", "sensor11", "sensor12"],
        mode: "OFF",
      },
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

