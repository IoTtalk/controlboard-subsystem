Vue.component('sensor-row', {
    props: ['sensors', 'value'],
    template: `
        {{sensors}}
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
    props: [],
    template: `
        <b-row class="text-left actuator-control">
            <b-col>
                <b-button-group>
                    <b-button size="md" variant="outline-secondary">
                    <b-form-checkbox switch disabled>Manual</b-form-checkbox>
                    </b-button>
                    <b-button variant="outline-secondary" pressed="true">Sensor</b-button>
                    <b-button variant="outline-secondary">Timer</b-button>
                </b-button-group>
                <span>Bulb</span>
            </b-col>
        </b-row>
    `
})

Vue.component('setting-area', {
    props: ['setting'],
    template: `
        <sensor-row
            
        ></sensor-row>
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