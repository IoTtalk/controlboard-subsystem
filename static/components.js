Vue.component('custom-sel', {
    props: ['options', 'select'],
    methods:{
        onSelect(val) {
            this.$emit("update-option", val);
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
    props: ['mode', 'actuator', 'dirty', 'sensors'],
    data: function() {
        return {
            state: false
        }
    },
    methods: {
        onSelectMode: function(nextMode) {
            if (0 === nextMode && true === this.state) {
                nextMode += 1;
            }
            this.$emit("update-mode", nextMode);
            return;
        },
        onUndo: function() {
            this.$emit("undo");
        },
        onSave: function() {
            this.$emit("save")
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
                            v-model="state"
                            v-on:input="onSelectMode(0)"
                        >Manual</b-form-checkbox>
                    </b-button>
                    <b-button variant="outline-success" 
                        v-bind:pressed="mode==='Sensor'"
                        v-bind:disabled="sensors===0"
                        v-on:click="onSelectMode(2)"
                    >Sensor</b-button>
                    <b-button variant="outline-success"
                        v-bind:pressed="mode==='Timer'"
                        v-on:click="onSelectMode(3)"
                    >Timer</b-button>
                </b-button-group>
                <span class="setting-test">{{actuator}}</span>
            </b-col>
            <div class="ml-auto" v-if="dirty"> 
                <b-button size="sm" variant="secondary" plain v-on:click="onUndo">Undo</b-button>
                <b-button size="sm" variant="primary" v-on:click="onSave">Save</b-button>
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
    props: ['projects', 'selected'],
    methods: {
        onSelectCB: function(projectIndex) {
            this.$emit("select-project", projectIndex);
            return;
        },
        
    },
    computed: {
        candicateProjects: function() {
            candicate = [];
            this.projects.forEach(element => {
                if (element.value !== this.selected) {
                    candicate.push(element);
                }
            });
            return candicate;
        },
        selectedProject: function() {
            selected = {
                "icon": "", "text": "", value: -1
            };
            this.projects.forEach(element => {
                console.log(element);
                if (element.value === this.selected) {
                    selected = element;
                }
            });
            return selected;
        }
    },
    template: `
        <div>
            <b-navbar-nav>
                <b-nav-item-dropdown v-on:toggle="$emit('pressed')">
                    <template v-slot:button-content v-if="projects.length!==0">
                        <b-img v-bind:src="selectedProject.icon"></b-img>
                        {{selectedProject.text}}
                    </template>
                    <template v-slot:button-content v-else>
                        Add ControlBoard
                    </template>
                    <project 
                        v-for="field in candicateProjects"
                        v-bind:field="field"
                        v-on:selectCB="onSelectCB(field.value)"
                        v-if="projects.length > 1"
                    ></project>
                </b-nav-item-dropdown>
            </b-navbar-nav>
        </div>
    `
})