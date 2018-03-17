#! /usr/bin/env python

import datetime
import subprocess
import time
import logging
from dateutil import parser as dparser
from win32 import win32api, win32ts
import os
import sqlite3

logger = logging.getLogger("checkLogins")

####################################################################
## numbers that are used for warnings and log outs of the
## restricted users

warnDuration = 6
cronPeriod = 5
replenish = 50

durationFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                            'checkLogins.db')
# print(durationFile)

#####################################################################

class UserDuration:
    def __init__(self, username, last_active=datetime.datetime.now(), 
                 minutes_remaining=replenish):
        self.username = username
        self.minutes_remaining = minutes_remaining
        self.last_active = last_active

    def __str__(self):
        return 'Duration({0},{1},{2})'.format(
            self.username, self.last_active, self.minutes_remaining)


def connectdb(filename = durationFile):
    if hasattr(connectdb, 'conn'):
        return getattr(connectdb, 'conn')
    
    conn = sqlite3.connect(filename)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                           'db_initialize.sql'), 'r') as sql:
        conn.executescript(sql.read())
    conn.commit()
    conn.row_factory = sqlite3.Row
    setattr(connectdb, 'conn', conn)
    return conn


def readDurationFile(filename = durationFile):
    conn = connectdb(filename)
    users = {}
    curs = conn.execute(('select username, last_active, minutes_remaining '
                         'from restricted_users;'))
    for row in curs:
        logger.debug(tuple(row))
        users[row['username']] = UserDuration(row['username'],
                                              dparser.parse(row['last_active']),
                                              row['minutes_remaining'])
    return users


def writeDurationFile(users, filename = durationFile):
    conn = connectdb(filename)
    rows = [ (u.last_active, u.minutes_remaining, u.username) 
             for u in users.values() ]
    with conn:
        conn.executemany(('update restricted_users '
                          'set last_active = ?, '
                          'minutes_remaining = ? '
                          'where username = ?'), rows)
    return True


def playNotification():
    #subprocess.call([
    #    'powershell', '-c',
    #    '(New-Object Media.SoundPlayer "C:\Windows\Media\chord.wav").PlaySync();'
    #])
    try:
        win32api.MessageBeep(0x00000010)
        win32api.Beep(880, 750)
    except:
        logger.info('cannot Beep')


def displayNotificationWindow(user):
    msgText = 'This is your warning.  You will be logged out ' +\
              'soon. Save your work now and logout to prevent data loss.'
    # subprocess.call(['env', 'DISPLAY={0}'.format(user.host),
    #                  'su','-c', "/usr/bin/notify-send "+\
    #                  "'Time Limit Warning' 'This is your "+\
    #                  "warning.  You will be logged out "+\
    #                  "soon." +\
    #                  "Save your work now and logout to " +\
    #                  "prevent data loss.'", username])
    win32ts.WTSSendMessage(win32ts.WTS_CURRENT_SERVER_HANDLE, 
                           findUserSession(user), 'Logout Notification',
                           msgText,
                           Style=0x00000000 | 0x00000030 | 0x00001000,
                           Timeout=15, Wait=False)
    # win32api.MessageBox(0, msgText, 'Logout Notification',
    #                     0x00000000 | 0x00000030 | 0x00001000)
    # subprocess.call(['msg', user, '/time:10', msgText])


def checkUsers(chkUsers, warn = warnDuration):
    checkTime = datetime.datetime.now()
    warnedUsers = {}
    for user in windows_users():
        # logger.debug(str(user))
        username = user.get('name', '').lower()
        if (user.get('state','').lower() == 'active'
            and username in chkUsers):
            elapsed_minutes = min(
                ((checkTime - chkUsers[username].last_active)/
                 datetime.timedelta(minutes=1)),
                cronPeriod)
            chkUsers[username].minutes_remaining = max(
                0, chkUsers[username].minutes_remaining - int(elapsed_minutes))
            chkUsers[username].last_active = checkTime
            logger.info(('user {} has used {:.3f} minutes for {} minutes '
                         'remaining').format(
                username,elapsed_minutes,chkUsers[username].minutes_remaining))
            if chkUsers[username].minutes_remaining <= warn:
                logger.warning('{} has been warned with {} remaining'.format(
                    username,chkUsers[username].minutes_remaining))
                playNotification()
                displayNotificationWindow(username)
                warnedUsers[username] = chkUsers[username]
    return warnedUsers


def disableUser(user):
    logger.info('locking user: {}'.format(user))
    # subprocess.call(['passwd', '-l', user])
    ret = subprocess.call(['net', 'user', user, '/active:no'])
    if ret != 0:
        logger.warning('failed to disable user {}: {}'.format(user, ret))
    return ret


def disableUsers(users):
    for user in users:
        disableUser(user)


def enableUser(user):
    logger.info('unlocking user: {}'.format(user))
    # subprocess.call(['passwd', '-u', user])
    ret = subprocess.call(['net', 'user', user, '/active:yes'])
    if ret != 0:
        logger.warning('failed to enable user {}: {}'.format(user, ret))
    return ret


def enableUsers(users):
    userDurations = readDurationFile()
    for user in users:
        ret = enableUser(user)
        if ret==0:
            try:
                userDurations[user].minutes_remaining = min(
                    180, userDurations[user].minutes_remaining + replenish)
            except:
                pass
    writeDurationFile(userDurations)


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


def log_windows_users():
    conn = connectdb()
    log_time = datetime.datetime.now()
    pars = [ (u['name'], log_time, u['state']) for u in windows_users()]
    with conn:
        conn.executemany(('insert into user_log values (?, ?, ?)'), pars)


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


def add_user(user):
    conn = connectdb()
    pars = (user,datetime.date.today()-datetime.timedelta(days=1),replenish,1)
    print(pars)
    try:
        with conn:
            conn.execute('insert into restricted_users values (?,?,?,?)',pars)
    except sqlite3.IntegrityError:
        pass


def restricted_users(min_stat=1):
    conn = connectdb()
    return [ r['username'] for r in conn.execute(
        'select username from restricted_users where manual_enable>=?', 
        (min_stat,)) ]


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
    parser.add_argument('--logout', metavar='user', #nargs=1,
                        help='Logout given user.')
    parser.add_argument('--add', metavar='user', #nargs=1,
                        help='Add restricted user.')
    parser.add_argument('--msg', action='store_true',
                        help='display the message and play the sound.')
    parser.add_argument('--verbose', action='store_true',
                        help='more verbose logging')
    args = parser.parse_args()
	
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

    fh = logging.FileHandler(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 
        'checkLogins.log'))
    fh.setFormatter(formatter)
    fh.setLevel(llevel)
    logger.addHandler(fh)

    log_windows_users()

    if args.enable != None:
        theUsers = restricted_users()
        if len(args.enable) > 0:
            theUsers = args.enable
        enableUsers(theUsers)
    elif args.disable != None:
        theUsers = restricted_users(0)
        if len(args.disable) > 0:
            theUsers = args.disable
        disableUsers(theUsers)
    elif args.add:
        logger.info('{} {}'.format(args.add, 'added to restricted'))
        add_user(args.add)
    elif args.all:
        savedDurations = readDurationFile()
        allDurations = dict(savedDurations)
        logged_in = windows_users()
        for u in windows_users():
            username = u['name']
            if not username in allDurations:
                allDurations[username] = UserDuration(username)
        for user in allDurations:
            logger.info(str(allDurations[user]))
        checkUsers(allDurations)
        for user in allDurations:
            logger.info(str(allDurations[user]))
        writeDurationFile(savedDurations)
    elif args.view:
        savedDurations = readDurationFile()
        for user in savedDurations:
            logger.info(str(savedDurations[user]))
    elif args.msg:
        playNotification()
        for u in windows_users():
            if u['state'] == 'Active':
                displayNotificationWindow(u['name'])
    elif args.logout:
        logger.info('{} {}'.format(args.logout, 'logging out'))
        logUserOut(args.logout)
    else:
        userDurations = readDurationFile()
        wusers = checkUsers(userDurations)
        writeDurationFile(userDurations)
        for user in wusers:
            disableUser(user)
            logger.info('{} {}'.format(user, wusers[user]))
            if wusers[user].minutes_remaining < 1:
                logUserOut(user)
