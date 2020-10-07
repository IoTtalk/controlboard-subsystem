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
      {icon: "../static/imgs/landscape.svg", name: "test_3"}
    ]
  }, 
  methods: {
    createField: function() {
      console.log("create field triggered");
    }
  }

})

