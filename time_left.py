from checkLogins import connectdb, windows_users
from win32 import win32api

def time_left(user):
    conn = connectdb()
    curs = conn.execute(
        'select minutes_remaining from restricted_users where username = ?', 
        (user,))
    for r in curs:
        win32api.MessageBox(
            0, '{} has {} minutes remaining.'.format(
                user, r['minutes_remaining']),
            'Time Remaining')


if __name__ == '__main__':
    import sys
    for u in windows_users():
        print('user: {} ({})'.format(u['name'], u['state']))
        if u['state'] == 'Active':
            time_left(u['name'])

    for u in sys.argv[1:]:
        print('user: {}'.format(u))
        time_left(u)

    # input('\nPress enter to exit.')