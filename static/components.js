Vue.component('project', {
    props: ['field'],
    template: `
        <b-img src="../static/imgs/landscape.svg"></b-img>
        <b-dropdown-item>{{field.name}}</b-dropdown-item>
    `
})

Vue.component('select-projects', {
    props: ['projects'],
    template: `
        <div>
            <b-navbar-nav>
                <b-nav-item-dropdown>
                    <template v-slot:button-content>
                        <b-img src="../static/imgs/landscape.svg"></b-img>
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