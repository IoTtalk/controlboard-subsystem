import threading


from flask import Flask
from pony import orm


import models


from config import env_config
from eventhandler import apis
from models import cb_db
from utils import connect_db, connect_zmq
from utils import make_logger
from utils import running_sa
from utils import register_ag
from utils import get_iottalk_info


@orm.db_session
def recover_sa(running_sa, config, logger):
    '''
    Recover SAs stored in Database.

    Args:
        running_sa: Dictionary used to record current AG SAs. Should be empty when passed in this function.
        config: Config object read from user specified .ini file.
        logger: Logger object to write log in.

    Returns:
        None
    '''
    assert len(running_sa) == 0
    to_recovered = cb_db.CB_SA.select()[:]
    print(to_recovered)

    for sa in to_recovered:
        status, ag_token = register_ag(sa, logger)
        if status:
            sa.ag_token = ag_token
            running_sa[sa.cb_id] = sa
    logger.info('Start Recovering SAs in Database......done')
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

    recover_sa(running_sa, env_config, system_logger)

    get_iottalk_info(system_logger)

    t = threading.Thread(target=connect_zmq, args=(system_logger,), daemon=True)
    t.start()

    app.run(
        host=env_config['env']['host'],
        port=env_config['env']['port'],
        threaded=True
    )
