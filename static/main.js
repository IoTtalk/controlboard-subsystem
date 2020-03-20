var app = new Vue({
  el: '#app',
  delimiters: ["<%", "%>"],
  data: {
    hours: ["00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23"],
    minuteAndSecond: ["00", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38", "39", "40", "41", "42", "43", "44", "45", "46", "47", "48", "49", "50", "51", "52", "53", "54", "55", "56", "57", "58", "59"],
    hamburgerActive: false,
    rules: [],
    sensordata: {},
    timeSave: {}
  },
  created: function () {
    self = this;
    this.getRules();
    this.$http.get('./current_data').then(
      response => {
        self.sensordata = response.body;
      }
    );
  },
  mounted: function () {
    // `this` points to the vm instance
    // GET /someUrl
    const self = this;
    this.datainterval = setInterval(
      function () {
        self.$http.get('/current_data').then(
          response => {
            self.sensordata = response.body; //get sensor data
            // console.log('current_data', self.sensordata);
          },
          response => {
            //error callback
          }
        )
      }, 1000
    );
    //todo change this to 15000 in production
    this.ruleInterval = setInterval(
      function () {
        self.getRules();
        console.log('fetching new rules');
      }, 60000);
  },
  methods: {
    getRules: function () {
      this.$http.get('/rules').then(
        response => {
          // console.log('get', response.body);
          this.rules = response.body;  //get rules data
          console.log('get rules', this.rules);
          this.rules.forEach(element => {
            if (element.rule_type === null) {
              element.rule_type = 'sensor';
              element.nullity = true;
            } else {
              element.nullity = false;
            }
            if (element.rule_type == 'sensor') {
              this.timeSave[element.actuator_alias] = {
                'time_open': "00:00:00",
                'time_close': "00:00:00"
              }
            } else {
              this.timeSave[element.actuator_alias] = {
                'time_open': element.time_open,
                'time_close': element.time_close
              }
            }
          });
        },
        response => {
          //error callback
        }
      );
    },
    checkingAbnormal: function (rule_object) {
      console.log('checking rule settings');
      console.log(rule_object);
      if (rule_object.rule_type === 'sensor') {
        if (rule_object.threshold_open < 0 || rule_object.threshold_close < 0) {
          console.log("negative error");
          return false;
        } else if (rule_object.comparison_open !== 'notset' && (rule_object.threshold_open === null || rule_object.threshold_open.length === 0)) {
          console.log("missing open value");
          return false;
        } else if (rule_object.comparison_close != 'notset' && (rule_object.threshold_close == null || rule_object.threshold_close.length === 0)) {
          console.log("missing close value");
          return false;
        }
      } else {
        if (rule_object.time_open == null || rule_object.time_close == null) {
          console.log("missing time");
          return false;
        } else if (rule_object.time_open == rule_object.time_close) {
          console.log("invalid time input")
          return false
        }
      }
      return true;
    },
    askingConfirm: function () { //call this function when hitting the confirm button 
      var valueAvailable = true;
      var new_rules = [];
      for (i = 0; i < this.rules.length; i++) {
        if (this.rules[i].changed === true) {
          console.log('modified rule detected', this.rules[i]);
          new_rules.push(this.rules[i]);
          this.rules[i].nullity = false;
        } else if (this.rules[i].nullity === true) {
          if (this.rules[i].rule_type == 'sensor') {
            if (this.rules[i].comparison_open != null || this.rules[i].comparison_close != null) {
              new_rules.push(this.rules[i]);
              console.log('modified rule detected', this.rules[i]);
              this.rules[i].nullity = false;
            }
          } else {
            new_rules.push(this.rules[i]);
            console.log('modified rule detected', this.rules[i]);
            this.rules[i].nullity = false;
          }
        }
      }
      console.log(new_rules);
      for (i = 0; i < new_rules.length; i++) {
        delete new_rules[i].nullity;
        delete new_rules[i].changed;
        if (new_rules[i].rule_type == 'timer') {
          new_rules[i].time_open = this.timeSave[new_rules[i].actuator_alias].time_open;
          new_rules[i].time_close = this.timeSave[new_rules[i].actuator_alias].time_close;
          new_rules[i].exetime = -1; // Should be removed once exetime can be set.
        }

        if (!this.checkingAbnormal(new_rules[i])) {
          console.log(i);
          valueAvailable = false;
        } //examine whether the input is available
      }
      if (!valueAvailable) {
        alert("設定值異常，請再次確認!!"); //input unavailable
        return;
      }

      this.$http.post('/new_rules', new_rules).then( //post data to rules
        response => {
          alert(response.body.msg);
          this.getRules();
        },
        response => {
          alert(response.body.msg);
          this.getRules();
        }
      ).catch(
        err => {
          console.log(err);
        }
      );
    },
    askingClear: function () { //call this function when hitting the clear button 
      if (confirm("清除全部設定?")) {
        this.$http.get('/stop').then( //call stop api
          response => {
            console.log('clear', response.body);
            alert(response.body.msg); //response.body has two properties, "msg" & "state"
            this.getRules(); // 重新抓回rules
          },
          response => {
            //error callback
          }
        )
      }
    },
    // handle value of time to separate selects
    timeHandler: function (time, type) {
      if (!time) {
        return "00";
      } else {
        switch (type) {
          case "hour":
            return time.split(":")[0]
          case "minute":
            return time.split(":")[1]
          case "second":
            return time.split(":")[2]
        }
      }
    },
    // handle sensor type change
    sensorTypeHandler: function (rule_index) {
      let result;
      switch (this.rules[rule_index].rule_type) {
        case "sensor":
          result = "timer"
          break;
        case "timer":
          result = "sensor"
          break;
      }
      this.rules[rule_index].rule_type = result;
      this.rules[rule_index].changed ? this.rules[rule_index].changed = false : this.rules[rule_index].changed = true;
    },
    hamburgerHandler: function () {
      this.hamburgerActive = !this.hamburgerActive
    },
    onChange: function (index) {
      this.rules[index].changed = true;

    },
    onTimeChange: function (index, event, type, turn) {
      console.log(event.target.value)
      this.rules[index].changed = true;
      actuator_alias = this.rules[index].actuator_alias;
      if (turn == 'open') {
        switch (type) {
          case 'hour':
            this.timeSave[actuator_alias].time_open = event.target.value.toString() + this.timeSave[actuator_alias].time_open.slice(2, 8);
            break;
          case 'minute':
            this.timeSave[actuator_alias].time_open = this.timeSave[actuator_alias].time_open.slice(0, 3) + event.target.value.toString() + this.timeSave[actuator_alias].time_open.slice(5, 8);
            break;
          case 'second':
            this.timeSave[actuator_alias].time_open = this.timeSave[actuator_alias].time_open.slice(0, 6) + event.target.value.toString();
            break;
        }
      } else {
        switch (type) {
          case 'hour':
            this.timeSave[actuator_alias].time_close = event.target.value.toString() + this.timeSave[actuator_alias].time_close.slice(2, 8);
            break;
          case 'minute':
            this.timeSave[actuator_alias].time_close = this.timeSave[actuator_alias].time_close.slice(0, 3) + event.target.value.toString() + this.timeSave[actuator_alias].time_close.slice(5, 8);
            break;
          case 'second':
            this.timeSave[actuator_alias].time_close = this.timeSave[actuator_alias].time_close.slice(0, 6) + event.target.value.toString();
            break;
        }
      }
    }
  }
})

