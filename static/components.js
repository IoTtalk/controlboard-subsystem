Vue.component('custom-sel', {
    props: ['options', 'index', 'content', 'select'],
    methods:{
        onSelect(val) {
            this.$emit("update-option", val, this.index, this.content);
            return;
        }
    },
    template: `
        <b-form-select required size="sm" class="custom-select"
            :options="options"
            v-on:change="onSelect"
            v-model="select"
        ></b-form-select>
    `
})

Vue.component('sensor-row', {
    props: ['sensors', 'value', 'status', 'mode', 'selected'],
    methods: {
        onSelectSensor: function (sensor) {
            var selected = this.sensors.indexOf(sensor);
            this.$emit("update-sensor", selected);
            return;
        }
    },
    computed: {
        candicateSensors: function() {
            candicate = [];
            this.sensors.forEach(element => {
                if (element !== this.sensors[this.selected]) {
                    candicate.push(element);
                }
            });
            return candicate;
        }
    },
    template: `
        <b-row v-bind:class="['sensor-list', status?'triggered':'']" class="text-left">
            <b-col align-self="start" text-align="start" class="pl-0">
                <b-dropdown v-if="mode=='Sensor'" v-bind:text="sensors[selected]" 
                    v-bind:variant="status?'danger':'success'"
                    v-bind:class="sensors[1]? '': 'one-item-dropdown'"
                >
                    <b-dropdown-item 
                        v-if="sensors.length > 1"
                        v-for="sensor in candicateSensors"
                        v-on:click="onSelectSensor(sensor)"
                    >{{sensor}}</b-dropdown-item>
                </b-dropdown>
                <b-dropdown class="one-item-dropdown"
                    v-if="mode==='Timer'" text='Timer' v-bind:variant="status?'danger':'success'"
                ></b-dropdown>
                <b-dropdown class="one-item-dropdown"
                    v-if="mode==='ON'" text='Manually Opened' v-bind:variant="status?'danger':'success'"
                ></b-dropdown>
                <b-dropdown class="one-item-dropdown"
                    v-if="mode==='OFF'" text='Manually Closed' v-bind:variant="status?'danger':'success'"
                ></b-dropdown>
            </b-col>
            <span><b>{{value}}</b></span>
        </b-row>
    `
})

Vue.component('actuator-row', {
    props: ['mode', 'actuator', 'dirty', 'index', 'sensors'],
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
                        v-bind:disabled="sensors===0"
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
            </div>
        </b-row>
    `
})


Vue.component('project', {
    props: ['field'],
    methods: {
        onSelectCB: function() {
            this.$emit("selectCB");
            return;
        }
    },
    template: `
        <b-dropdown-item
            v-on:click="onSelectCB"
        >   <b-img v-bind:src="field.icon"></b-img>
            {{field.text}}
        </b-dropdown-item>
    `
})

Vue.component('select-projects', {
    props: ['projects'],
    methods: {
        onSelectCB: function(projectIndex) {
            var temp = this.projects[0];
            this.$set(this.projects, 0, this.projects[projectIndex]);
            this.$set(this.projects, projectIndex, temp);
            console.log(this.projects);
            return;
        }
    },
    template: `
        <div>
            <b-navbar-nav>
                <b-nav-item-dropdown>
                    <template v-slot:button-content v-if="projects.length!==0">
                        <b-img v-bind:src="projects[0].icon"></b-img>
                        {{projects[0].text}}
                    </template>
                    <template v-slot:button-content v-else>
                        Add ControlBoard
                    </template>
                    <project 
                        v-for="(field, index) in projects.slice(1)"
                        v-bind:field="field"
                        v-on:selectCB="onSelectCB(index)"
                        v-if="projects.length > 1"
                    ></project>
                </b-nav-item-dropdown>
            </b-navbar-nav>
        </div>
    `
})