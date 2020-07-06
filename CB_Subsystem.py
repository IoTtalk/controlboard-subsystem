from flask import Flask


import models


from eventhandler import apis
from utils import config
from utils import connect_db
from utils import make_logger
from utils import test_db
from utils import running_sa


def recover_sa(running_sa, config, logger):
    '''
    Recover SAs stored in Database.
    TODO: Apply AG DA generation after AG subsystem complete.
    Args:
        sa_dict: Dictionary used to record current AG SAs. Should be empty when passed in this function.
        config: Config object read from user specified .ini file.
        logger: Logger object to write log in.

    Returns:
        None
    '''
    logger.info('Start Recovering SAs in Database...')
    assert len(running_sa) == 0



    return


if __name__ == "__main__":
    system_logger = make_logger('System', 'system')
    system_logger.info('Start Launching ControlBoard Subsystem......')

    app = Flask(__name__)
    system_logger.info('\tCreating Server\t\t......done')

    app.register_blueprint(apis)
    system_logger.info('\tCreating EventHandler\t......done')

    connect_db(system_logger, models.cb_db)
    test_db(system_logger)

    recover_sa(running_sa, config, system_logger)

    app.run(
        host=config['env']['host'],
        port=config['env']['port'],
        threaded=True
    )
