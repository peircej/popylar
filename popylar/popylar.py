import os.path as op
import sys
import platform
import requests
import uuid
import configparser
import threading
import logging


popylar_path = op.join(op.expanduser('~'), '.popylar')

# create a session so that we can adde user-agent headers
session = requests.Session()


def set_user_agent(ua_string=None, app='popylar', version=None):
    """Set the user-agent of the session to contain information about the system

    Either provide a full user-agent string of your own 
    (e.g. https://developers.whatismybrowser.com/useragents/explore/operating_system_name/linux/)
    or specify your app name/version 
    """
    if not ua_string:
        # start with the app name
        agentStr = app
        # add a version number if appropriate
        if app == 'popylar' and not version:
            version = __version__
        if version:
            agentStr += "/{}".format(version)
        # then add platform info in parenths
        if sys.platform == 'darwin':
            ver = '.'.join(platform.mac_ver()[0].split('.')[:-1])  # e.g. 10.6
            agentStr += " (Macintosh; Intel Mac OS X {})".format(ver)
        elif sys.platform == 'win32':
            if platform.architecture()[0] == '64bit':
                arch = 'x64'
            else:
                arch = 'x86'
            ver = '.'.join(platform.win32_ver()[1].split('.')[:-1])
            agentStr += " (Windows NT {}; {})".format(ver, arch)
        elif sys.platform.startswith('linux'):
            arch = platform.machine()
            dist, ver = platform.dist()
            ver = '.'.join(platform.distr.split('.')[:-1])
            agentStr += " (X11; Linux {}; {})".format(ver, arch)
    logging.debug('user-agent: {}'.format(agentStr))
    session.headers.update({'user-agent': agentStr})


def get_or_create_config():
    if not op.exists(popylar_path):
        parser = configparser.ConfigParser()
        parser.read_dict(dict(user=dict(uid=uuid.uuid1().hex,
                                        track=True)))
        with open(popylar_path, 'w') as fhandle:
            parser.write(fhandle)
    else:
        parser = configparser.ConfigParser()
        parser.read(popylar_path)

    return parser


def opt_out():
    """Permanently opt-out of Popylar tracking.

    To opt-in again, run ``popylar.reset_uid()``
    """
    parser = get_or_create_config()
    parser['user']['track'] = "False"
    with open(popylar_path, 'w') as fhandle:
        parser.write(fhandle)


def reset_uid():
    """Opt-in to popylar tracking, and/or reset the user id"""
    parser = get_or_create_config()
    parser.read_dict(dict(user=dict(uid=uuid.uuid1().hex,
                                    track=True)))
    with open(popylar_path, 'w') as fhandle:
        parser.write(fhandle)


def opt_in():
    """Opt-in to popylar tracking"""
    if not _get_uid():
        reset_uid()


def _get_uid():
    parser = get_or_create_config()
    if parser['user'].getboolean('track'):
        uid = parser['user']['uid']
    else:
        uid = False
    return uid


def _do_it(data, timeout):
    try:
        response = session.post('http://www.google-analytics.com/collect',
                                 data=data, timeout=timeout)
        return response
    except:
        return False


def track_event(tracking_id, category, action, uid=None, label=None, value=0,
                software_version=None, timeout=2, thread=True):
    """
    Record an event with Google Analytics

    Parameters
    ----------
    tracking_id : str
        Google Analytics tracking ID.
    category : str
        Event category.
    action : str
        Event action.
    uid : str
        User unique ID, assigned when popylar was installed.
    label : str
        Event label.
    value : int
        Event value.
    software_version : str
        Records a version of the software.
    timeout : float
        Maximal duration (in seconds) for the network connection to track the
        event. After this duration has elapsed with no response (e.g., on a
        slow network connection), the tracking is dropped.
    """
    # If no user unique ID provided, try to get one from popylar_path:
    if uid is None:
        uid = _get_uid()

    # If it's stil None, assume that the user has opted out
    # (by running popylar.opt_out() or editing the config file)
    if not uid:
        return False

    # Based on https://cloud.google.com/appengine/docs/python/google-analytics
    # and:  https://developers.google.com/analytics/devguides/collection/protocol/v1/devguide  # noqa
    data = {'v': '1',  # API version.
            'tid': tracking_id,  # GA tracking ID
            'cid': uid,  # User unique ID, stored in `popylar_path`
            't': 'event',  # Event hit type.
            'ec': category,  # Event category.
            'ea': action,  # Event action.
            'el': label,  # Event label.
            'ev': value,  # Event value, must be an integer
            # We hijack "app version" to report the package version:
            'av': software_version}
    if thread:
        t = threading.Thread(target=_do_it, args=(data, timeout))
        # No return value!
        t.start()
        return None
    else:
        return _do_it(data, timeout)
