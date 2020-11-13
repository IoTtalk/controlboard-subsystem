Vue.component('custom-sel', {
    props: ['options'],
    template: `
        <b-form-select required size="sm" class="custom-select"
        :options="options"
        ></b-form-select>
    `
})

Vue.component('sensor-row', {
    props: ['sensors', 'value'],
    template: `
        <b-row class="sensor-list text-left">
            <b-col align-self="start" text-align="start">
                <b-dropdown v-bind:text="sensors[0]" variant="danger">
                    <b-dropdown-item v-for="sensor in sensors.slice(1)">
                        {{sensor}}
                    </b-dropdown-item>
                </b-dropdown>
            </b-col>
            <span><b>{{value}}</b></span>
        </b-row>
    `
})

Vue.component('actuator-row', {
    props: ['mode', 'actuator'],
    template: `
        <b-row class="text-left actuator-control">
            <b-col>
                <b-button-group>
                    <b-button size="md" variant="outline-success">
                        <b-form-checkbox switch 
                            v-bind:disabled="(mode==='Sensor' || mode==='Timer')"
                        >Manual</b-form-checkbox>
                    </b-button>
                    <b-button variant="outline-success" 
                        v-bind:pressed="mode==='Sensor'"
                    >Sensor</b-button>
                    <b-button variant="outline-success"
                        v-bind:pressed="mode==='Timer'"
                    >Timer</b-button>
                </b-button-group>
                <span class="setting-test">{{actuator}}</span>
            </b-col>
            <div class="ml-auto"> 
                <b-button size="sm" variant="secondary" plain>Undo</b-button>
                <b-button size="sm" variant="secondary">Save</b-button>
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