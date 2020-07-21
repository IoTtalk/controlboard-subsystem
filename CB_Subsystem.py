from flask import Flask
from pony import orm


import models


from config import env_config
from eventhandler import apis
from models import cb_db
from utils import connect_db
from utils import make_logger
from utils import test_db
from utils import running_sa
from utils import register_ag



@orm.db_session()
def recover_sa(running_sa, config, logger):
    '''
    Recover SAs stored in Database.
    TODO: Apply AG DA generation after AG subsystem complete.
    Args:
        running_sa: Dictionary used to record current AG SAs. Should be empty when passed in this function.
        config: Config object read from user specified .ini file.
        logger: Logger object to write log in.

    Returns:
        None
    '''
    logger.info('Start Recovering SAs in Database...')
    assert len(running_sa) == 0
    to_recovered = cb_db.CB_SA.select()[:]
    print(to_recovered)

    for sa in to_recovered:
        register_ag(sa, logger)
    print(running_sa)
    return


if __name__ == "__main__":
    system_logger = make_logger('System', 'system')
    system_logger.info('Start Launching ControlBoard Subsystem......')

    app = Flask(__name__)
    system_logger.info('\tCreating Server\t\t......done')

    app.register_blueprint(apis)
    system_logger.info('\tCreating EventHandler\t......done')

    connect_db(system_logger, models.cb_db)
    # test_db(system_logger)

    recover_sa(running_sa, env_config, system_logger)

    app.run(
        host=env_config['env']['host'],
        port=env_config['env']['port'],
        threaded=True
    )
