Vue.component('custom-sel', {
    props: ['options', 'select', 'status'],
    methods:{
        onChange(val) {
            this.$emit("update-option", val);
        }
    },
    template: `
        <b-form-select required size="sm" class="custom-select"
            :options="options"
            @change="onChange"
            :value="select"
            :disabled="!status"
        ></b-form-select>
    `
})

Vue.component('actuator-row', {
    props: ['actuator', 'status'],
    template: `
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
    template: `
        <b-row class="text-left sensor-list">
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
                        v-bind:pressed="mode==='Timer'"
                        v-on:click="onSelectMode(3)"
                    >Timer</b-button>
                    <b-button variant="outline-success" 
                        v-bind:pressed="mode==='Sensor'"
                        v-on:click="onSelectMode(2)"
                    >{{sensor}}</b-button>
                </b-button-group>
            </b-col>
            <span class="ml-auto mr-1"><b>{{value}}</b></span>
        </b-row>
    `
})


Vue.component('sensor-condition-row', {
    props: ["comparisons", "currentCb","on-select-compare", "setting"],
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
    watch:{
        sensorCod:{
            handler(val, oldVal){
                console.log(this.setting);
                this.$emit('update-sensor-cod', {
                    ruleID: this.setting.ruleID,
                    data: this.sensorCod
                })
            },
            deep:true
        }
    },
    template: `
        <div class="card border-dark" style="margin-bottom: 20px;">
            <div class="card-header">
                {{setting}}
                <span class="ml-auto mr-1"><b>val</b></span>
            </div>
            <div class="card-body">
                <div class="setting-sensor">
                    <custom-sel
                        :options="comparisons"
                        :select="sensorCod.comparisonOpen"
                        :status="currentCb.status"
                        @update-option="sensorCod.comparisonOpen = $event"
                    ></custom-sel>
                    <b-form-input size="sm" class="custom-input"
                        v-model="sensorCod.comparisonOpenInput"
                    ></b-form-input>
                    <span class="setting-text-mid">ON.</span>
                    <custom-sel
                        :options="comparisons"
                        :select="sensorCod.comparisonClose"
                        :status="currentCb.status"
                        @update-option="sensorCod.comparisonClose = $event"
                    ></custom-sel> 
                    <b-form-input size="sm" class="custom-input"
                        v-model="sensorCod.comparisonCloseInput"
                    ></b-form-input>
                    <span class="setting-text">OFF.</span>
                </div>
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
    template: `
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