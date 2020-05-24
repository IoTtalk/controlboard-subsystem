from flask import Blueprint
from flask import render_template

apis = Blueprint('api', __name__)

@apis.route('/')
def hello():
    return 'Hello World'