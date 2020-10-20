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

