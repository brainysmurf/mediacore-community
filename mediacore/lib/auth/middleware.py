# This file is a part of MediaCore CE (http://www.mediacorecommunity.org),
# Copyright 2009-2013 MediaCore Inc., Felix Schwarz and other contributors.
# For the exact contribution history, see the git revision log.
# The source code contained in this file is licensed under the GPLv3 or
# (at your option) any later version.
# See LICENSE.txt in the main project directory, for more information.

import re

from repoze.who.classifiers import default_challenge_decider, default_request_classifier
from repoze.who.middleware import PluggableAuthenticationMiddleware
from repoze.who.plugins.auth_tkt import AuthTktCookiePlugin
from repoze.who.plugins.friendlyform import FriendlyFormPlugin
from repoze.who.plugins.sa import SQLAlchemyAuthenticatorPlugin
from mediacore.config.routing import login_form_url, login_handler_url, \
    logout_handler_url, post_login_url, post_logout_url
from pylons.controllers.util import Request
from mediacore.lib.auth.permission_system import MediaCorePermissionSystem

from mediacore.model import User, Group
import imaplib
import ldap
import re
import datetime
from mediacore.model.meta import DBSession
from sqlalchemy.exc import IntegrityError

__all__ = ['add_auth', 'classifier_for_flash_uploads']

class GeneralAuth(object):
    def __init__(self, config):
        """ Give this object whatever keys are in config: host, etc """
        self.__dict__.update(config)
        restricted_group_name = "RestrictedGroup"
        self.restricted_group = DBSession.query(Group).filter(Group.group_name.in_([restricted_group_name])).first()
        self.builtin_editor_group = DBSession.query(Group).filter(Group.group_id.in_([2])).first()

        if not self.restricted_group:
            make_new_group = Group(name=restricted_group_name, display_name=restricted_group_name)
            # Copy the permissions from the same group that can give us access to the /admin section
            from copy import copy
            make_new_group.permissions = copy(builtin_editor_group.permissions)
            DBSession.add(make_new_group)
            DBSession.flush()
            # get the group we just created
            self.restricted_group = DBSession.query(Group).filter(Group.group_name.in_([restricted_group_name])).first()

    def __del__(self):
        self.delete()

    def auth(self, username, password):
        if not hasattr(self, 'connection'):    
            self.connection = self.init()
        return bool(self.login(username, password))

    def log(self, exception):
        #TODO: Implement
        print(str(exception))

    def init(self):
        """ Should return the connection object """
        raise NotImplemented

    def delete(self):
        """ Should free self.connection """
        raise NotImplemented

    def login(self, username, password):
        """ Return bool whether or not user username with password authenticates """
        raise NotImplemented

    def default_domain(self):
        raise NotImplemented

    def default_group(self):
        raise NotImplemented

class LDAPAuthentication(GeneralAuth):

    def init(self):
        trace_level = 1 if hasattr(self, 'trace_level') and self.trace_level else 0
        return ldap.initialize(self.host, trace_level=trace_level)

    def delete(self):
        self.connection.unbind()

    def login(self, username, password):
        try:
            return self.connection.simple_bind_s("{cnword}={uid},{ouphrase},{dcphrase}".format(
                cnword=self.cnword, uid=username,
                ouphrase=self.ouphrase, dcphrase=self.dcphrase), password)
        except Exception, e:
            self.log(e)
            return False

    def default_domain(self):
        return self.default_email_domain if hasattr(self. 'default_email_domain') else "@example.org"

    def default_group(self):
        return self.builtin_editor_group

class IMAPAuthentication(GeneralAuth):

    def init(self):
        return imaplib.IMAP4(self.host, trace_level=trace_level)

    def delete(self):
        pass

    def login(self, username, password):
        try:
            return self.connection.login(username, password)
        except Exception, e:
            self.log(e)
            return False

    def default_domain(self):
        return "@{}".format(self.host)

    def default_group(self):
        return self.restricted_group

class MediaCoreAuthenticatorPlugin(SQLAlchemyAuthenticatorPlugin):
    def __init__(self, config, *args, **kwargs):
        super(SQLAlchemyAuthenticatorPlugin, self).__init__(*args, **kwargs)
        self.config = config
        self.imap_auth = self.config['imap']
        self.ldap_auth = self.config['ldap']

    def authenticate(self, environ, identity, notagain=False):
        login = super(MediaCoreAuthenticatorPlugin, self).authenticate(environ, identity)
        if login is None:
            if notagain:
                return None   # prevent infinite loop

            username = identity['login']
            password = identity['password']
            imap_connected, ldap_connected = (False, False)
            is_student, is_teacher = (False, False)

            if re.match(r'^[a-z]+[0-9]{2}$', username):
                auth_to_use = self.imap_auth
            else:
                auth_to_use = self.ldap_auth
                
            if not auth_to_use.auth(username, password):
                return None
            else:

                # Use the model to create the user which automagically gets put in the database
                user = User()
                user.display_name = username
                user.user_name = username
                user.email_address = "{}{}".format(user.user_name, auth_to_use.default_domain())
                user.password = u'uselesspassword#%^^#@'
                user.groups = auth_to_use.default_group()

                try:
                    #actually add the user
                    DBSession.add(user)
                    DBSession.commit()
                except IntegrityError:
                    DBSession.rollback()

                # Now repoze.who should be able to login
                return self.authenticate(environ, identity, notagain=True)

        user = self.get_user(login)
        # The return value of this method is used to identify the user later on.
        # As the username can be changed, that's not really secure and may 
        # lead to confusion (user is logged out unexpectedly, best case) or 
        # account take-over (impersonation, worst case).
        # The user ID is considered constant and likely the best choice here.
        return user.user_id
    
    @classmethod
    def by_attribute(cls, config, attribute_name=None):
        from mediacore.model import DBSession, User
        authenticator = MediaCoreAuthenticatorPlugin(config, User, DBSession)
        if attribute_name:
            authenticator.translations['user_name'] = attribute_name
        return authenticator


class MediaCoreCookiePlugin(AuthTktCookiePlugin):
    def __init__(self, secret, **kwargs):
        if kwargs.get('userid_checker') is not None:
            raise TypeError("__init__() got an unexpected keyword argument 'userid_checker'")
        kwargs['userid_checker'] = self._check_userid
        super(MediaCoreCookiePlugin, self).__init__(secret, **kwargs)
    
    def _check_userid(self, user_id):
        # only accept numeric user_ids. In MediaCore < 0.10 the cookie contained
        # the user name, so invalidate all these old sessions.
        if re.search('[^0-9]', user_id):
            return False
        return True


def who_args(config):
    auth_by_username = MediaCoreAuthenticatorPlugin.by_attribute(config, 'user_name')
    
    form = FriendlyFormPlugin(
        login_form_url,
        login_handler_url,
        post_login_url,
        logout_handler_url,
        post_logout_url,
        rememberer_name='cookie',
        charset='iso-8859-1',
    )
    cookie_secret = config['sa_auth.cookie_secret']
    seconds_30_days = 30*24*60*60 # session expires after 30 days
    cookie = MediaCoreCookiePlugin(cookie_secret, 
        cookie_name='authtkt', 
        timeout=seconds_30_days, # session expires after 30 days
        reissue_time=seconds_30_days/2, # reissue cookie after 15 days
    )
    
    who_args = {
        'authenticators': [
            ('auth_by_username', auth_by_username)
        ],
        'challenge_decider': default_challenge_decider,
        'challengers': [('form', form)],
        'classifier': classifier_for_flash_uploads,
        'identifiers': [('main_identifier', form), ('cookie', cookie)],
        'mdproviders': [],
    }
    return who_args


def authentication_middleware(app, config):
    return PluggableAuthenticationMiddleware(app, **who_args(config))


class AuthorizationMiddleware(object):
    def __init__(self, app, config):
        self.app = app
        self.config = config
    
    def __call__(self, environ, start_response):
        environ['mediacore.perm'] = \
            MediaCorePermissionSystem.permissions_for_request(environ, self.config)
        return self.app(environ, start_response)


def add_auth(app, config):
    authorization_app = AuthorizationMiddleware(app, config)
    return authentication_middleware(authorization_app, config)


def classifier_for_flash_uploads(environ):
    """Normally classifies the request as browser, dav or xmlpost.

    When the Flash uploader is sending a file, it appends the authtkt session
    ID to the POST data so we spoof the cookie header so that the auth code
    will think this was a normal request. In the process, we overwrite any
    pseudo-cookie data that is sent by Flash.

    TODO: Currently overwrites the HTTP_COOKIE, should ideally append.
    """
    classification = default_request_classifier(environ)
    if classification == 'browser' \
    and environ['REQUEST_METHOD'] == 'POST' \
    and 'Flash' in environ.get('HTTP_USER_AGENT', ''):
        session_key = environ['repoze.who.plugins']['cookie'].cookie_name
        # Construct a temporary request object since this is called before
        # pylons.request is populated. Re-instantiation later comes cheap.
        request = Request(environ)
        try:
            session_id = request.str_POST[session_key]
            environ['HTTP_COOKIE'] = '%s=%s' % (session_key, session_id)
        except KeyError:
            pass
    return classification
