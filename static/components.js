Vue.component('custom-sel', {
    props: ['options', 'selected'],
    methods:{
        onTimingSelect(val) {
            console.log(val);
            this.$set(this, "selected", val);
            return;
        }
    },
    template: `
        <b-form-select required size="sm" class="custom-select"
            :options="options"
            v-model="selected"
            v-on:change="onTimingSelect"
        ></b-form-select>
    `
})

Vue.component('sensor-row', {
    props: ['sensors', 'value', 'index', 'status'],
    methods: {
        onSelectSensor: function (idx) {
            var temp = this.sensors[0];
            this.$set(this.sensors, 0, this.sensors[idx]);
            this.$set(this.sensors, idx, temp);
            return;
        }
    },
    template: `
        <b-row v-bind:class="['sensor-list', status?'triggered':'']" class="text-left">
            <b-col align-self="start" text-align="start">
                <b-dropdown v-bind:text="sensors[0]" v-bind:variant="status?'success':'danger'">
                    <b-dropdown-item 
                        v-for="(sensor, idx) in sensors.slice(1)"
                        v-on:click="onSelectSensor(idx + 1)"
                    >{{sensor}}</b-dropdown-item>
                </b-dropdown>
            </b-col>
            <span><b>{{value}}</b></span>
        </b-row>
    `
})

Vue.component('actuator-row', {
    props: ['mode', 'actuator', 'dirty', 'index'],
    methods: {
        onSelectMode: function(nextMode) {
            this.$emit("update-mode", nextMode, this.index);
            return;
        }
    },
    template: `
        <b-row class="text-left actuator-control">
            <b-col>
                <b-button-group>
                    <b-button size="md" variant="outline-success"
                        v-bind:pressed="mode==='ON' || mode==='OFF'"
                    >
                        <b-form-checkbox switch 
                            v-on:input="onSelectMode(0)"
                        >Manual</b-form-checkbox>
                    </b-button>
                    <b-button variant="outline-success" 
                        v-bind:pressed="mode==='Sensor'"
                        v-on:click="onSelectMode(1)"
                    >Sensor</b-button>
                    <b-button variant="outline-success"
                        v-bind:pressed="mode==='Timer'"
                        v-on:click="onSelectMode(2)"
                    >Timer</b-button>
                </b-button-group>
                <span class="setting-test">{{actuator}}</span>
            </b-col>
            <div class="ml-auto" v-if="dirty"> 
                <b-button size="sm" variant="secondary" plain>Undo</b-button>
                <b-button size="sm" variant="primary">Save</b-button>
            <div>
        </b-row>
    `
})


Vue.component('project', {
    props: ['field'],
    template: `
        <b-dropdown-item align-self="start">
            <b-img v-bind:src="field.icon"></b-img>
            {{field.name}}
        </b-dropdown-item>
    `
})

Vue.component('select-projects', {
    props: ['projects'],
    template: `
        <div>
            <b-navbar-nav>
                <b-nav-item-dropdown right>
                    <template v-slot:button-content>
                        <b-img v-bind:src="projects[0].icon"></b-img>
                        {{projects[0].name}}
                    </template>
                    <project 
                        v-for="field in projects.slice(1)"
                        v-bind:field="field"
                    ></project>
                </b-nav-item-dropdown>
            </b-navbar-nav>
        </div>
    `
})