from cb_manager import cb_manager
import shared_vars
# there is a dict of cb_id, cb_name
@app.before_first_request
def init():
    # input uuid and d_name
    manager = cb_manager()
    return
@app.route('/')
def index():
    pass

@app.route('/new_rules', methods=['POST'])
def fun1():
    pass

@app.route('/stop')



@app.route('/rules', methods=['GET'])

@app.route('/current_data', methods=['GET'])
