from SMWinservice.SMWinservice import SMWinservice
import datetime
import logging
import os
import traceback, sys
import win32event

from checkLogins import monitor_users, enable_all_users, last_system_enable

logger = logging.getLogger(__name__)

class CheckLoginService(SMWinservice):
    _svc_name_ = 'CheckLoginService'
    _svc_display_name_ = 'Login time monitor'
    _svc_description_ = 'A service to monitor time time limits of users'

    CHECK_AFTER_MINUTES = 5
    TIME_OUT_WAIT = CHECK_AFTER_MINUTES*60*1000

    def __init__(self, args):
        super().__init__(args)
        self.is_running = False
        self.last_check = None
        self.last_enabled = datetime.datetime.now()

    def start(self):
        log_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'checkLogins.log')

        logging.basicConfig(
            filename=log_file,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S")
        self.is_running = True
        self.last_check = (datetime.datetime.now() 
                - datetime.timedelta(minutes=2*self.CHECK_AFTER_MINUTES))
        self.last_enabled = last_system_enable()
        logger.info("starting service with last_check: {}".format(self.last_check))

    def stop(self):
        logger.info("stopping service")
        self.is_running = False

    def main(self):
        needed_sleep = self.TIME_OUT_WAIT
        while self.is_running:
            try:
                rc = win32event.WaitForSingleObject(self.hWaitStop, needed_sleep)
                if rc == win32event.WAIT_OBJECT_0:
                    self.is_running = False
                    logger.info('received stop: {}'.format(rc))
                    break
                curr_run = datetime.datetime.now()
                if (curr_run - self.last_check >= datetime.timedelta(minutes=self.CHECK_AFTER_MINUTES)):
                    monitor_users(self.CHECK_AFTER_MINUTES)
                    self.last_check = curr_run
                if ((curr_run.date() > self.last_enabled.date())
                    and (curr_run.time() > datetime.time(hour=8))):
                    enable_all_users()
                    self.last_enabled = curr_run
                needed_sleep = int(self.TIME_OUT_WAIT-(datetime.datetime.now()-curr_run)/datetime.timedelta(milliseconds=1))
                if needed_sleep < 0:
                    needed_sleep = 1000
                # logger.info('hearbeat and sleep sleep for {}ms'.format(needed_sleep))
            except Exception:
                exc_type, exc_val, exc_tb = sys.exc_info()
                exc_strings = traceback.format_exception(exc_type, exc_val, exc_tb)
                logger.error("Caught an exception:\n{}".format(''.join(exc_strings)))
                raise

        logger.info("finished main loop: {}".format(self.is_running))


if __name__ == '__main__':
    CheckLoginService.parse_command_line()
