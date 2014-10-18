import psutil
import json
import datetime

import logging

logger = logging.getLogger('timingTest')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(message)s",
                              datefmt='%Y-%m-%d %H:%M:%S')
fh = logging.FileHandler(r'C:\checkLogins\timingTest.log')
fh.setFormatter(formatter)
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)

checkTime = datetime.datetime.now()

logger.info('checking at {}'.format(checkTime))

for user in psutil.users():
    loginTime = datetime.datetime.fromtimestamp(user.started)
    loginDuration = checkTime - loginTime
    logger.info('{} logged in a {} for {}'.format(
        user.name, loginTime, loginDuration))
