#! /usr/bin/env python

import datetime
import subprocess
import time
import pickle
import re
import logging
import dateutil.parser
from win32 import win32api, win32ts
import psutil
import os

logger = logging.getLogger("checkLogins")

####################################################################
## numbers that are used for warnings and log outs of the
## restricted users

warnDuration = datetime.timedelta(minutes=45)
logoutDuration = datetime.timedelta(minutes=50)
stopWarnDuration = warnDuration + datetime.timedelta(minutes=10)

cronPeriod = datetime.timedelta(minutes=5)

restrictedUsers = ['grant', 'max', 'rose', 'seth']
manualUsers = []
#restrictedUsers = []
allUsers = restrictedUsers + manualUsers + ['jake', 'candi']
durationFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'restrictedDurations.pkl')
# print(durationFile)

#####################################################################

class UserDuration:
    def __init__(self, username, duration = datetime.timedelta(minutes=0), date = None):
        self.username = username
        self.loginDuration = duration
        self.lastCheck = date

    def __str__(self):
        return 'Duration({0},{1},{2})'.format(
            self.username, self.loginDuration, self.lastCheck)


checkTime = datetime.datetime.now()
# userDurations = dict(zip(restrictedUsers, [None]*len(restrictedUsers)))
# allDurations = dict(zip(allUsers, [None]*len(allUsers)))
userDurations = { u:UserDuration(u) for u in restrictedUsers+manualUsers }
allDurations = { u:UserDuration(u) for u in allUsers }

def readDurationFile(filename = durationFile):
    users = allDurations
    try:
        with open(filename, 'rb') as f:
            rdur = pickle.load(f)
            for u in rdur:
                # print(str(rdur[u]))
                if ((rdur[u].lastCheck is not None) and
                    (rdur[u].lastCheck.date() == datetime.date.today())):
                    users[u] = rdur[u]
    except FileNotFoundError:
        pass
    except:
        raise
    return users

def writeDurationFile(filename = durationFile, users = userDurations):
    with open(filename, 'wb') as f:
        pickle.dump(users, f)
    return True

def playNotification(user = None, host = None):
    #subprocess.call([
    #    'powershell', '-c',
    #    '(New-Object Media.SoundPlayer "C:\Windows\Media\chord.wav").PlaySync();'
    #])
    win32api.Beep(880, 750)

def displayNotificationWindow(user = None, host = None):
    msgText = 'This is your warning.  You will be logged out ' +\
              'soon. Save your work now and logout to prevent data loss.'
    # subprocess.call(['env', 'DISPLAY={0}'.format(user.host),
    #                  'su','-c', "/usr/bin/notify-send "+\
    #                  "'Time Limit Warning' 'This is your "+\
    #                  "warning.  You will be logged out "+\
    #                  "soon." +\
    #                  "Save your work now and logout to " +\
    #                  "prevent data loss.'", username])
    try:
        subprocess.call(['msg', user, '/time:10', msgText])
    except FileNotFoundError:
        win32ts.WTSSendMessage(win32ts.WTS_CURRENT_SERVER_HANDLE, 
                               findUserSession(user), 'Logout Notification',
                               msgText,
                               Style=0x00000000 | 0x00000030 | 0x00001000,
                               Timeout=15, Wait=False)
        # return win32api.MessageBox(0, msgText, "Logout Notification", 
                                   # 0x00001000 | 0x00000030 | 0x00200000)

def checkUsers(chkUsers, warn = warnDuration, noMoreWarn = stopWarnDuration):
    warnedUsers = {}
    for user in windows_users():
        # logger.debug(str(user))
        username = user.get('name', '').lower()
        if (user.get('state','').lower() == 'active'
            and username in chkUsers):
            lastCheck = chkUsers[username].lastCheck
            if (lastCheck is None) or (lastCheck.date() != datetime.date.today()):
                lastCheck = checkTime

            storedDuration = chkUsers[username].loginDuration

            loginDuration = storedDuration + min(cronPeriod, 
                max(checkTime-lastCheck, datetime.timedelta(minutes=0)))

            chkUsers[username].lastCheck = checkTime
            chkUsers[username].loginDuration = loginDuration
            logger.info('user {} logged in for {}'.format(
                username, loginDuration))
            if (loginDuration > warn):
                # if (loginDuration.total_seconds() < noMoreWarn):
                logger.warning('{} has been warned after {}'.format(
                    username,loginDuration))
                playNotification(username)
                displayNotificationWindow(username)
                warnedUsers[username] = chkUsers[username]
    return warnedUsers

def disableUser(user):
    logger.info('locking user: {}'.format(user))
    # subprocess.call(['passwd', '-l', user])
    subprocess.call(['net', 'user', user, '/active:no'])

def disableUsers(users):
    for user in users:
        disableUser(user)

def enableUser(user):
    logger.info('unlocking user: {}'.format(user))
    # subprocess.call(['passwd', '-u', user])
    subprocess.call(['net', 'user', user, '/active:yes'])

def enableUsers(users = restrictedUsers):
    global userDurations
    userDurations = readDurationFile(durationFile)
    for user in users:
        enableUser(user)
        try:
            userDurations[user] = UserDuration(user)
        except:
            pass
    writeDurationFile(durationFile, userDurations)

def findUserSession(user):
    for cuser in windows_users():
        if cuser.get('name','').lower() == user:
            return cuser['session']
    logger.info('user: {} session not found'.format(user))
    return ''

def windows_users():
    user_sessions = win32ts.WTSEnumerateSessions()
    logged_in_users = []
    for s in user_sessions:
        username = win32ts.WTSQuerySessionInformation(
            win32ts.WTS_CURRENT_SERVER_HANDLE,
            s['SessionId'], 5).strip()
        if len(username) > 0:
            logged_in_users.append({
                'name': username,
                'session': s['SessionId'],
                'state': 'Active' if s['State'] == 0 else 'Disc'})
    return logged_in_users


def logUserOut(user):
    # sigs = ['-15', '-15', '-9', '-9']
    sigi = 0
    usid = findUserSession(user)
    while userLoggedIn(user) and (sigi < 4):
        logger.info('logging out {}'.format(user))
        win32ts.WTSLogoffSession(win32ts.WTS_CURRENT_SERVER_HANDLE,
            usid, False)
        time.sleep(60)
        sigi += 1


def userLoggedIn(user):
    for cuser in windows_users():
        if cuser.get('name','').lower() == user:
            logger.info('{} still logged in {}'.format(user, cuser))
            return True
    logger.info('{} is gone.'.format(user))
    return False


if __name__ == '__main__':
    import argparse
    desc = """Monitor and enforce quotas.\n
    Supply --enable to enable users.\n
    Supply --disable to disable users.\n
    Monitoring will be applied otherwise"""
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('--enable', nargs='*', metavar='user',
                        help='users to enable.  If none specified enable all')
    parser.add_argument('--disable', nargs='*', metavar='user',
                        help='users to disable.  If none specified sidable all')
    parser.add_argument('--all', action='store_true',
                        help='check all users')
    parser.add_argument('--view', action='store_true',
                        help='Show values that have been stored so far.')
    parser.add_argument('--logout', metavar='user', nargs=1,
                        help='Logout given user.')
    parser.add_argument('--msg', action='store_true',
                        help='display the message and play the sound.')
    parser.add_argument('--verbose', action='store_true',
                        help='more verbose logging')
    args = parser.parse_args()
	
    import sys
    # output_f = open(r'C:\checkLogins\script_output.txt', 'a+')
    # sys.stdout = output_f
    # sys.stderr = output_f

    # logger.debug('currently logged in:')
    # for user in windows_users():
    #     logger.debug('{}'.format(user))
    llevel = logging.INFO
    if args.verbose:
        llevel = logging.DEBUG
    logger.setLevel(llevel)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s",
                                  datefmt="%Y-%m-%d %H:%M:%S")
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    ch.setLevel(llevel)
    logger.addHandler(ch)

    fh = logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'checkLogins.log'))
    fh.setFormatter(formatter)
    fh.setLevel(llevel)
    logger.addHandler(fh)

    if args.enable != None:
        theUsers = restrictedUsers
        if len(args.enable) > 0:
            theUsers = args.enable
        enableUsers(theUsers)
    elif args.disable != None:
        theUsers = restrictedUsers + manualUsers
        if len(args.disable) > 0:
            theUsers = args.disable
        disableUsers(theUsers)
    elif args.all:
        savedDurations = readDurationFile(durationFile)
        allDurations = { u:savedDurations[u] for u in allDurations }
        for user in allDurations:
            logger.info(str(allDurations[user]))
        checkUsers(allDurations, warnDuration, datetime.timedelta(hours=24))
        for user in allDurations:
            # logger.info(str(allDurations[user]))
            savedDurations.update(allDurations)
        for user in savedDurations:
            logger.info(str(savedDurations[user]))
        writeDurationFile(durationFile, savedDurations)
    elif args.view:
        savedDurations = readDurationFile(durationFile)
        for user in savedDurations:
            logger.info(str(savedDurations[user]))
    elif args.msg:
        playNotification('jake')
        displayNotificationWindow('jake')
    elif args.logout:
        logger.info('{} {}'.format(args.logout, 'logging out'))
        logUserOut(args.logout)
    else:
        savedDurations = readDurationFile(durationFile)
        userDurations = { u:savedDurations[u] for u in userDurations }
        wusers = checkUsers(userDurations)
        savedDurations.update(userDurations)
        writeDurationFile(durationFile, savedDurations)
        for user in wusers:
            disableUser(user)
            logger.info('{} {}'.format(user, wusers[user]))
            if wusers[user].loginDuration > logoutDuration:
                logUserOut(user)
	
    # output_f.close()
