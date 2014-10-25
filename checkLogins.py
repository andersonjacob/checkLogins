#! /usr/bin/env python

import psutil
import datetime
import subprocess
import time
import pickle
import re
import logging

logger = logging.getLogger("checkLogins")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")
ch = logging.StreamHandler()
ch.setFormatter(formatter)
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)

####################################################################
## numbers in seconds that are used for warnings and log outs of the
## restricted users

warnDuration = datetime.timedelta(minutes=40)
logoutDuration = datetime.timedelta(minutes=45)
stopWarnDuration = warnDuration + datetime.timedelta(minutes=10)

cronPeriod = datetime.timedelta(minutes=5)

restrictedUsers = ['seth', 'grant', 'max', 'rose']
#restrictedUsers = []
allUsers = restrictedUsers + ['jake', 'candi', 'uande18']
durationFile = r'C:\checkLogins\restrictedDurations.pkl'

fh = logging.FileHandler(r'C:\checkLogins\checkLogins.log')
fh.setFormatter(formatter)
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)

#####################################################################

class UserDuration:
    def __init__(self, username, date = None, duration = None,
                 lastLogin = None, lastDuration = None):
        self.username = username
        self.loginDuration = duration
        self.loginTime = date
        self.lastLogin = lastLogin
        self.lastDuration = lastDuration

    def __str__(self):
        return 'Duration({0},{1},{2},{3},{4})'.format(
            self.username, self.loginTime, self.loginDuration,
            self.lastLogin, self.lastDuration)


checkTime = datetime.datetime.now()
# userDurations = dict(zip(restrictedUsers, [None]*len(restrictedUsers)))
# allDurations = dict(zip(allUsers, [None]*len(allUsers)))
userDurations = { u:UserDuration(u) for u in restrictedUsers }
allDurations = { u:UserDuration(u) for u in allUsers }

def readDurationFile(filename = durationFile):
    users = allDurations
    try:
        f = open(filename, 'rb')
        rdur = pickle.load(f)
        for u in rdur:
            if (rdur[u].loginTime) and \
               (rdur[u].loginTime.date() == datetime.date.today()):
                users[u] = rdur[u]
    except:
        pass
    return users

def writeDurationFile(filename = durationFile, users = userDurations):
    f = open(filename, 'wb')
    pickle.dump(users, f)
    return True

def lastToDurations(users = userDurations):
    logins = subprocess.check_output(['last','-F']).split('\n')
    for login in logins:
        words = login.split()
        if len(words) < 8:
            continue
        user = words[0]
        terminal = words[1]
        if re.search(r':[0-9]', terminal) and user in users:
            logger.debug(str(login.split()))
            logintime = datetime.datetime.strptime(' '.join(words[4:8]),
                                                   '%b %d %H:%M:%S %Y')
            if (logintime.date() < datetime.date.today()):
                return users
            try:
                logouttime = datetime.datetime.strptime(' '.join(words[10:14]),
                                                   '%b %d %H:%M:%S %Y')
            except ValueError:
                if words[-2] == 'crash':
                    logger.debug('{} after {}'.format(words[-2],words[-1]))
                    logouttime = logintime + \
                                 datetime.timedelta(hours=int(words[-1][1:3]),
                                                    minutes=int(words[-1][4:6]))
                else:
                    logouttime = checkTime
            logger.info('{} login: {} to {}'.format(user,logintime,logouttime))
            if (not users[user].lastLogin):
                users[user].lastLogin = logintime
            if users[user].loginDuration:
                users[user].loginDuration += (logouttime-logintime)
            else:
                users[user].loginDuration = logouttime-logintime

    return users

def playNotification(user = None, host = None):
    subprocess.call([
        'powershell', '-c', 
        '(New-Object Media.SoundPlayer "C:\Windows\Media\chord.wav").PlaySync();'
    ])

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
    subprocess.call(['msg', user, '/time:10', msgText])

def checkUsers(chkUsers, warn = warnDuration, noMoreWarn = stopWarnDuration):
    warnedUsers = {}
    for user in psutil.users():
        # logger.debug(str(user))
        username = user.name.lower()
        if (not user.terminal) or re.search(r':[0-9]', user.terminal):
            loginTime = datetime.datetime.fromtimestamp(user.started)
            loginDuration = checkTime - loginTime
            logger.debug('{} logged in at {} for {}'.format(
                username, loginTime, loginDuration))
            if username in chkUsers:
                # logger.debug('{} loginTime: {}'.format(
                #     chkUsers[username], loginTime))
                storedTime = chkUsers[username].loginTime
                if storedTime and (storedTime >= loginTime):
                    loginTime = storedTime
                if (storedTime == None) and (loginDuration > cronPeriod):
                    loginTime = checkTime
                loginDuration = checkTime-loginTime
                lastLogin = chkUsers[username].lastLogin
                if (lastLogin) and (lastLogin < loginTime) and \
                   (chkUsers[username].loginDuration != None):
                    chkUsers[username].lastDuration = chkUsers[username].loginDuration
                    chkUsers[username].lastLogin = chkUsers[username].loginTime
                    loginDuration += chkUsers[username].loginDuration
                elif chkUsers[username].lastDuration:
                    loginDuration += chkUsers[username].lastDuration
                chkUsers[username].loginTime = loginTime
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
    sessions = subprocess.check_output(['qwinsta'], 
                                       universal_newlines = True).split()
    try:
        return sessions[sessions.index(user)+1]
    except ValueError:
        logger.info('user: {} session not found'.format(user))
        return ''

def logUserOut(user):
    sigs = ['-15', '-15', '-9', '-9']
    logger.info('logging out {}'.format(user))
    sigi = 0
    while userLoggedIn(user) and (sigi < len(sigs)):
        logger.info("sending signal {} to user {}".format(sigs[sigi],user))
        # subprocess.call(['pkill', sigs[sigi], '-u', user])
        if sigs[sigi] == sigs[0]:
            session = findUserSession(user)
            subprocess.call(['logoff', str(session)])
        else:
            subprocess.call(['shutdown','/l','/t', '10'])
        time.sleep(30)
        sigi += 1

def userLoggedIn(user):
    for cuser in psutil.get_users():
        if cuser.name.lower() == user:
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
    parser.add_argument('--last', action='store_true',
                        help='use last command to determine durations for today.')
    parser.add_argument('--view', action='store_true',
                        help='use last command to determine durations for today.')
    args = parser.parse_args()
	
    import sys
    # output_f = open(r'C:\checkLogins\script_output.txt', 'a+')
    # sys.stdout = output_f
    # sys.stderr = output_f

    # logger.debug('running checkLogins')
    if args.enable != None:
        theUsers = restrictedUsers
        if len(args.enable) > 0:
            theUsers = args.enable
        enableUsers(theUsers)
    elif args.disable != None:
        theUsers = restrictedUsers
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
            logger.info(str(allDurations[user]))
            savedDurations.update(allDurations)
        writeDurationFile(durationFile, savedDurations)
    elif args.last:
        loadedUsers = lastToDurations()
        for user in loadedUsers:
            logger.info(str(loadedUsers[user]))
        writeDurationFile(filename = durationFile, users = loadedUsers)
    elif args.view:
        savedDurations = readDurationFile(durationFile)
        for user in savedDurations:
            logger.info(str(savedDurations[user]))
    else:
        savedDurations = readDurationFile(durationFile)
        userDurations = { u:savedDurations[u] for u in userDurations }
        wusers = checkUsers(userDurations)
        savedDurations.update(userDurations)
        writeDurationFile(durationFile, savedDurations)
        for user in wusers:
            disableUser(user)
            if wusers[user].loginDuration > logoutDuration:
                logUserOut(user)
	
    # output_f.close()
