#! /usr/bin/env python

import datetime
import subprocess
import time
import pickle
import re
import logging
import dateutil.parser
# from win32 import win32api

logger = logging.getLogger("checkLogins")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")
ch = logging.StreamHandler()
ch.setFormatter(formatter)
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)

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
allUsers = restrictedUsers + manualUsers + ['jake', 'candi', 'uande18']
durationFile = r'C:\checkLogins\restrictedDurations.pkl'

fh = logging.FileHandler(r'C:\checkLogins\checkLogins.log')
fh.setFormatter(formatter)
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)

#####################################################################

class UserDuration:
    def __init__(self, username, date = None, duration = 0,
                 lastLogin = None, lastDuration = None):
        self.username = username
        self.loginDuration = duration
        self.loginTime = date

    def __str__(self):
        return 'Duration({0},{1},{2})'.format(
            self.username, self.loginTime, self.loginDuration)


checkTime = datetime.datetime.now()
# userDurations = dict(zip(restrictedUsers, [None]*len(restrictedUsers)))
# allDurations = dict(zip(allUsers, [None]*len(allUsers)))
userDurations = { u:UserDuration(u) for u in restrictedUsers+manualUsers }
allDurations = { u:UserDuration(u) for u in allUsers }

def readDurationFile(filename = durationFile):
    users = allDurations
    try:
        f = open(filename, 'rb')
        rdur = pickle.load(f)
        for u in rdur:
            if ((rdur[u].loginDuration > 0) and
                (rdur[u].loginTime.date() == datetime.date.today())):
                users[u] = rdur[u]
    except:
        pass
    return users

def writeDurationFile(filename = durationFile, users = userDurations):
    f = open(filename, 'wb')
    pickle.dump(users, f)
    return True

# def lastToDurations(users = userDurations):
#     logins = subprocess.check_output(['last','-F']).split('\n')
#     for login in logins:
#         words = login.split()
#         if len(words) < 8:
#             continue
#         user = words[0]
#         terminal = words[1]
#         if re.search(r':[0-9]', terminal) and user in users:
#             logger.debug(str(login.split()))
#             logintime = datetime.datetime.strptime(' '.join(words[4:8]),
#                                                    '%b %d %H:%M:%S %Y')
#             if (logintime.date() < datetime.date.today()):
#                 return users
#             try:
#                 logouttime = datetime.datetime.strptime(' '.join(words[10:14]),
#                                                    '%b %d %H:%M:%S %Y')
#             except ValueError:
#                 if words[-2] == 'crash':
#                     logger.debug('{} after {}'.format(words[-2],words[-1]))
#                     logouttime = logintime + \
#                                  datetime.timedelta(hours=int(words[-1][1:3]),
#                                                     minutes=int(words[-1][4:6]))
#                 else:
#                     logouttime = checkTime
#             logger.info('{} login: {} to {}'.format(user,logintime,logouttime))
#             if (not users[user].lastLogin):
#                 users[user].lastLogin = logintime
#             if users[user].loginDuration:
#                 users[user].loginDuration += (logouttime-logintime)
#             else:
#                 users[user].loginDuration = logouttime-logintime

#     return users

def playNotification(user = None, host = None):
    subprocess.call([
        'powershell', '-c',
        '(New-Object Media.SoundPlayer "C:\Windows\Media\chord.wav").PlaySync();'
    ])
    # win32api.Beep(880, 750)

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
    #return win32api.MessageBox(0, msgText, "Logout Notification")

def checkUsers(chkUsers, warn = warnDuration, noMoreWarn = stopWarnDuration):
    warnedUsers = {}
    for user in windows_users():
        # logger.debug(str(user))
        username = user.get('name', '').lower()
        if user.get('state','').lower() == 'active':
            loginTime = dateutil.parser.parse(user.get('started', ''))
            loginDuration = checkTime - loginTime
            # logger.debug('{} logged in at {} current duration {}'.format(
            #     username, loginTime, loginDuration))
            if username in chkUsers:
                # logger.debug('{} loginTime: {}'.format(
                #     chkUsers[username], loginTime))
                if loginTime.date() != datetime.date.today():
                    loginTime = checkTime

                storedDuration = chkUsers[username].loginDuration

                loginDuration = (storedDuration + 1)*cronPeriod

                chkUsers[username].loginTime = loginTime
                chkUsers[username].loginDuration = storedDuration+1
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
    try:
        users = subprocess.check_output(['query', 'user'], 
                                        universal_newlines=True)
    except subprocess.CalledProcessError as e:
        users = e.output
    users = users.split('\n')
    header = users.pop(0)
    logged_in_users = []
    for l in users:
        if len(l) >= len(header):
            username = l[header.find('USERNAME'):header.find('SESSIONNAME')].strip()
            session_id = l[header.find('ID'):header.find('STATE')].strip()
            state = l[header.find('STATE'):header.find('IDLE TIME')].strip()
            logon_time = l[header.find('LOGON TIME'):].strip()
            logged_in_users.append({'name': username, 'session': session_id, 
                                    'state': state, 'started': logon_time})
    return logged_in_users



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
            logger.info(str(allDurations[user]))
            savedDurations.update(allDurations)
        writeDurationFile(durationFile, savedDurations)
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
            logger.info('{} {}'.format(user, wusers[user]))
            if wusers[user].loginDuration*cronPeriod > logoutDuration:
                logUserOut(user)
            else:
                logger.info('{} only warned after {}'.format(
                    user, wusers[user].loginDuration*cronPeriod))
	
    # output_f.close()
