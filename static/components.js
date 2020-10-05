Vue.component('project', {
    props: ['project'],
    template: `
        <img src="project.iconPath">
        <b-dropdown-item>project.name/<b-dropdown-item>
    `
})

Vue.component('select-projects', {
    props: ['projects'],
    template: `
        <div>
            <b-navbar-nav>
                <!-- Navbar dropdowns -->
                <slot></slot>
                <b-nav-item-dropdown v-bind:text="projects[0].name">
                    <project 
                        v-for="project in projects.slice(1)"
                        project="project"
                    ></project>
                </b-nav-item-dropdown>
            </b-navbar-nav>
        </div>
    `
})