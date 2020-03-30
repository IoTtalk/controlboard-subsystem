from cb_instance import cb_instance
import models

class cb_manager():
    def init():
        #read cb instance from database
        instances = models.CB_Instances.select_all()
        for instance in instances:
            #cb instance initiate with id and device name, make a dict to keep track
            some_dict[instance.cb_id, instance.cb_name] = cb_instance(instance.cb_id, instance.cb_name)
        return

    def create_instance()

    def delete_instance()

    def mod_instance_rules()

    def stop_instance()

    

    