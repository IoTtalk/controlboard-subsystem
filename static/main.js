var app = new Vue({
  el: '#app',
  delimiters: ["<%", "%>"],
  data: {
    projects: [
      {icon: '../static/imgs/landscape.svg', name: 'Hello World'},
      {icon: '../static/imgs/landscape.svg', name: 'test_1'},
      {icon: '../static/imgs/landscape.svg', name: 'test_2'}
    ]
  }

})

