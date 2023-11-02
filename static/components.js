Vue.component('custom-sel', {
    props: ['options', 'select', 'status'],
    methods:{
        onChange(val) {
            this.$emit("update-option", val);
        }
    },
    template: /*html*/`
        <b-form-select required size="sm" class="custom-select"
            :options="options"
            @change="onChange"
            :value="select"
            :disabled="!status"
        ></b-form-select>
    `
})

Vue.component('custom-sel-sensor-comparison', {
    props: ['select', 'options', 'status'],
    computed: {
        selectValue: {
            get(){
                return this.select
            },
            set(val){
                this.$emit('update:select', val)
            },
        }
    },
    template: /*html*/`
        <b-form-select required size="sm" class="custom-select"
            :options="options"
            :disabled="!status"
            v-model="selectValue"
        ></b-form-select>
    `
})


Vue.component('actuator-row', {
    props: ['actuator', 'status'],
    template: /*html*/`
        <b-row v-bind:class="['element-status', status?'triggered':'']" class="text-left">
            <b-col align-self="start" text-align="start" class="pl-0">
                <b-dropdown class="one-item-dropdown"
                    v-bind:text="actuator" v-bind:variant="status?'danger':'success'"
                ></b-dropdown>
            </b-col>
        </b-row>
    `
})

Vue.component('sensor-row', {
    props: ['mode', 'sensor', 'value', 'dirty'],
    data: function() {
        return {
            state: (this.mode==="ON")? true: false
        }
    },
    methods: {
        onSelectMode: function(nextMode) {
            if (0 === nextMode && true === this.state) {
                nextMode += 1;
            }
            this.$emit("update-mode", nextMode);
            return;
        }
    },
    template: /*html*/`
        <b-row class="text-left sensor-list">
            <b-col>
                <b-button-group>
                    <!-- <b-button size="md" variant="outline-success"
                        v-bind:pressed="mode==='ON' || mode==='OFF'"
                    >
                        <b-form-checkbox switch
                            v-model="state"
                            v-on:input="onSelectMode(0)"
                        >Manual</b-form-checkbox>
                    </b-button> -->
                    <b-button variant="outline-success"
                        v-bind:pressed="mode==='Timer'"
                        v-on:click="onSelectMode(3)"
                    >Timer</b-button>
                    <b-button variant="outline-success" 
                        v-bind:pressed="mode==='Sensor'"
                        v-on:click="onSelectMode(2)"
                    >Sensor</b-button>
                </b-button-group>
            </b-col>
            <!-- <span class="ml-auto mr-1"><b>{{value}}</b></span> -->
        </b-row>
    `
})

Vue.component('sensor-condition-row', {
    props: {
        comparisons: {
            type: Array
        },
        currentCb: {
            type: Object
        },
        onSelectCompare: {
            type: Function
        },
        sensor:{
            type: Object
        },
        value:{
            type: Object
        }
    },
    methods: {
        onClickOperator: function() {
            this.sensor.operation = (this.sensor.operation === "AND") ? "OR" : "AND";
        },
    },
    data(){
        return{
            sensorCod:{
                comparisonOpen: '',
                comparisonOpenInput: '',
                comparisonClose: '',
                comparisonCloseInput: '',
            }
        }
    },
    template: /*html*/`
        <div>
            <div class="card border-dark" style="margin-bottom: 20px;">
                <div class="card-header d-flex">
                    <!-- {{sensor}} {{sensor.selectedSensor}} -->
                    {{sensor.sensorName}} 
                    <span class="ml-auto mr-1"><b>{{ value[sensor.selectedSensor] }}</b></span>
                </div>
                <div class="card-body">
                    <div class="setting-sensor">
                        <custom-sel-sensor-comparison
                            :options="comparisons"
                            :status="currentCb.status"
                            :select.sync="sensor.openSensor"
                        ></custom-sel-sensor-comparison>
                        <b-form-input size="sm" class="custom-input"
                            v-model="sensor.openSensorVal"
                        ></b-form-input>
                        <span class="setting-text-mid">ON.</span>
                        <custom-sel-sensor-comparison
                            :options="comparisons"
                            :status="currentCb.status"
                            :select.sync="sensor.closeSensor"
                        ></custom-sel-sensor-comparison> 
                        <b-form-input size="sm" class="custom-input"
                            v-model="sensor.closeSensorVal"
                        ></b-form-input>
                        <span class="setting-text">OFF.</span>
                    </div>
                </div>
            </div>
            <div v-if="sensor.is_show_operation" style="margin-bottom: 20px;">
                <b-button @click="onClickOperator">{{ sensor.operation }}</b-button>
                <!-- <p>Pressed State: <strong>{{ sensor.operation }}</strong></p> -->
            </div>
        </div>
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
    template: /*html*/`
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
        onShow: function(bvEvent) {
            if (this.projects.length <= 1) {
                bvEvent.preventDefault();
            }
            return;
        }
        
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
    template: /*html*/`
        <div>
            <b-navbar-nav>
                <b-nav-item-dropdown v-on:toggle="$emit('pressed')" v-on:show="onShow">
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