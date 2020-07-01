import datetime
import logging
import os
import sys
import time


from flask import Flask
from flask import jsonify
from flask import request
from flask import render_template


import models


from eventhandler import apis
from utils import config
from utils import connect_db
from utils import make_logger


def recover_sa(config, logger):
    '''
    Recover SAs stored in Database.
    TODO: Apply AG DA generation after AG subsystem complete.
    Args:
        config: Config object read from user specified .ini file.
        logger: Logger object to write log in.

    Returns:
        None
    '''
    config_path = str(sys.argv[1])

    config = configparser.ConfigParser()
    config.read(config_path)

    print(config['IoTtalk']['serverip'])

    return


if __name__ == "__main__": 
    system_logger = make_logger('System', 'system')
    system_logger.info('Start Launching ControlBoard Subsystem......')

    app = Flask(__name__)
    system_logger.info('\tCreating Server\t\t......done')

    app.register_blueprint(apis)
    system_logger.info('\tCreating EventHandler\t......done')

    connect_db(system_logger, models.cb_db)



    app.run(
        host=config['env']['host'],
        port=config['env']['port'],
        threaded=True
    )
