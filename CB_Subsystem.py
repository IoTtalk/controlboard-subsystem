import atexit
import threading


from datetime import timedelta


from flask import Flask
from pony import orm


import models


from config import env_config, default_status
from eventhandler import apis
from models import CB
from oauth import oauth2_client
from utils import connect_db, connect_zmq
from utils import make_logger, register_ag, deregister_ag, get_iottalk_info
from utils import running_cb, running_status
# from utils import test_db


@orm.db_session
def recover_sa(running_cb, logger):
    '''
    Recover SAs stored in Database.

    Args:
        running_cb: Dictionary used to record current AG SAs. Should be empty when passed in this function.
        logger: Logger object to write log in.

    Returns:
        None
    '''
    assert len(running_cb) == 0
    to_recovered = CB.select()[:]
    print('SA in Database ', to_recovered)

    for sa in to_recovered:
        status, ag_token = register_ag(sa, logger)
        if status:
            sa.ag_token = ag_token
            running_cb[sa.sa_id] = sa
            for rule in sa.rule_set:
                running_status[rule.rule_id] = default_status
    logger.info('Start Recovering SAs in Database......done')
    print(running_cb)
    return


@orm.db_session
def on_exit(logger, running_cb):
    logger.info("Closing Subsystem......")
    logger.info("\tDeregistering all running SAs")
    for sa_id in running_cb:
        status = deregister_ag(CB_SA[sa_id], logger)
        if not status:
            logger.warning(f"Deregistration for SA Device for {CB_SA[sa_id].sa_name} failed")
    logger.info("Subsystem closed")
    return


if __name__ == "__main__":
    system_logger = make_logger('System', 'system')
    system_logger.info('Start Launching ControlBoard Subsystem......')

    app = Flask(__name__)
    app.config.update(
        SESSION_COOKIE_SAMESITE=None,
        # SESSION_COOKIE_SECURE=True,  # for https only
        SESSION_COOKIE_HTTPONLY=True
    )
    app.secret_key = 'asdaldkjalskdjllkd'
    system_logger.info('\tCreating Server\t\t......done')

    oauth2_client.init_app(app)
    oauth2_client.register(
        name="iottalk",
        client_id=env_config["oauth"]["client_id"],
        client_secret=env_config["oauth"]["client_secret"],
        server_metadata_url=env_config["oauth"]["openid_url"],
        client_kwargs={"scope": "openid"}
    )
    system_logger.info('\tRegister OAuth2.0 resource\t...done')

    app.register_blueprint(apis)
    system_logger.info('\tCreating EventHandler\t......done')

    connect_db(system_logger, models.cb_db)
    recover_sa(running_cb, system_logger)

    get_iottalk_info(system_logger)

    t = threading.Thread(target=connect_zmq, args=(system_logger,), daemon=True, name='status_collector')
    t.start()
    system_logger.info('Start Creating status collector thread......done')
    atexit.register(on_exit, logger=system_logger, running_cb=running_cb)

    app.run(
        host=env_config['env']['host'],
        port=env_config['env']['port'],
        threaded=True
    )
