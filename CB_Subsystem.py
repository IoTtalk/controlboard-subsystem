import atexit
import threading


from datetime import timedelta


from flask import Flask
from pony import orm


import models


from config import env_config, default_status
from eventhandler import apis
from models import CB_SA, CB_Account
from utils import connect_db, connect_zmq
from utils import make_logger, register_ag, deregister_ag, get_iottalk_info
from utils import running_sa, running_status


@orm.db_session
def recover_sa(running_sa, logger):
    '''
    Recover SAs stored in Database.

    Args:
        running_sa: Dictionary used to record current AG SAs. Should be empty when passed in this function.
        logger: Logger object to write log in.

    Returns:
        None
    '''
    assert len(running_sa) == 0
    to_recovered = CB_SA.select()[:]
    print('SA in Database ', to_recovered)

    for sa in to_recovered:
        status, ag_token = register_ag(sa, logger)
        if status:
            sa.ag_token = ag_token
            running_sa[sa.sa_id] = sa
            for rule in sa.rule_set:
                running_status[rule.rule_id] = default_status
    logger.info('Start Recovering SAs in Database......done')
    print(running_sa)
    return


@orm.db_session
def on_exit(logger, running_sa):
    logger.info("Closing Subsystem......")
    logger.info("\tDeregistering all running SAs")
    for sa_id in running_sa:
        status = deregister_ag(CB_SA[sa_id], logger)
        if not status:
            logger.warning(f"Deregistration for SA Device for {CB_SA[sa_id].sa_name} failed")
    logger.info("Subsystem closed")
    return


if __name__ == "__main__":
    system_logger = make_logger('System', 'system')
    system_logger.info('Start Launching ControlBoard Subsystem......')

    app = Flask(__name__)
    app.secret_key = 'asdaldkjalskdjllkd'
    app.permanent_session_lifetime = timedelta(minutes=30)
    system_logger.info('\tCreating Server\t\t......done')

    app.register_blueprint(apis)
    system_logger.info('\tCreating EventHandler\t......done')

    connect_db(system_logger, models.cb_db)
    recover_sa(running_sa, system_logger)

    get_iottalk_info(system_logger)

    t = threading.Thread(target=connect_zmq, args=(system_logger,), daemon=True, name='status_collector')
    t.start()
    system_logger.info('Start Creating status collector thread......done')
    atexit.register(on_exit, logger=system_logger, running_sa=running_sa)

    with orm.db_session:
        if 0 == len(CB_Account.select()):
            admin = CB_Account(account=env_config["env"]["admin"], privilege=2)
            system_logger.info(f"Init Admin with account {admin.account}")

    app.run(
        host=env_config['env']['host'],
        port=env_config['env']['port'],
        threaded=True
    )
