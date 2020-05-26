from flask import Blueprint
from flask import jsonify
from flask import render_template
from flask import request


apis = Blueprint('api', __name__)


@apis.route('/<cb_id>/')
def render_SA(cb_id):
    '''
    Render SA template of the SA with specified cb_id.

    Args:
        cb_id: ID of the requester SA.

    Returns:
        Rendered HTML template of the SA.
        Status code: 200.
    '''
    return 'Hello World'


@apis.route('/<cb_id>/new_rules', methods=['POST'])
def set_rules(cb_id):
    '''
    Set the rules contained in the request sent from the specified SA.

    Args:
        cb_id: ID of the requester SA.
        
    Returns:
        Status code: 200.
    '''
    pass


@apis.route('/<cb_id>/stop', methods=['GET'])
def stop_SA(cb_id):
    '''
    Stop all actuator execution and pends the SA with specified cb_id.

    Args:
        cb_id: ID of the requester SA.

    Returns:
        Status code: 200.
        message: 'Stop Done'.
    '''
    pass


@apis.route('/<cb_id>/rules', methods=['GET'])
def get_rules(cb_id):
    '''
    Get the rules contained in the specified SA.

    Args:
        cb_id: ID of the requester SA.

    Returns:
        Status code: 200.
        rule_list: A list containing rules of the specific SA.
                   Each element of this list is a rule in dictionary format and it's current status and mode.

    '''
    return jsonify()


@apis.route('/<cb_id>/current_data', methods=['GET'])
def get_datum(cb_id):
    '''
    Get the datum of sensors manipulated by the specified SA.

    Args:
        cb_id: ID of the requester SA.

    Returns:
        Status code: 200.
        record_list: A json object containing the lastest data of each sensor.
    '''
    record_list = list()
    return 


