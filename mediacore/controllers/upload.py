# This file is a part of MediaCore CE (http://www.mediacorecommunity.org),
# Copyright 2009-2013 MediaCore Inc., Felix Schwarz and other contributors.
# For the exact contribution history, see the git revision log.
# The source code contained in this file is licensed under the GPLv3 or
# (at your option) any later version.
# See LICENSE.txt in the main project directory, for more information.

import simplejson as json

from pylons import request, tmpl_context
from pylons.controllers.util import abort

from mediacore.forms.uploader import UploadForm
from mediacore.lib import email
from mediacore.lib.base import BaseController
from mediacore.lib.decorators import autocommit, expose, observable, validate
from mediacore.lib.helpers import redirect, url_for
from mediacore.lib.storage import add_new_media_file
from mediacore.lib.thumbnails import create_default_thumbs_for, has_thumbs
from mediacore.model import Author, DBSession, get_available_slug, Media
from mediacore.plugin import events
from mediacore.model import User, Group
import datetime

import logging
log = logging.getLogger(__name__)

upload_form = UploadForm(
    action = url_for(controller='/upload', action='submit'),
    async_action = url_for(controller='/upload', action='submit_async')
)

class UploadController(BaseController):
    """
    Media Upload Controller
    """

    def __before__(self, *args, **kwargs):
        if not request.settings['appearance_enable_user_uploads']:
            abort(404)
        result = BaseController.__before__(self, *args, **kwargs)
        # BareBonesController will set request.perm
        if not request.perm.contains_permission('upload'):
            abort(404)
        return result

    @expose('upload/index.html')
    @observable(events.UploadController.index)
    def index(self, **kwargs):
        """Display the upload form.

        :rtype: Dict
        :returns:
            legal_wording
                XHTML legal wording for rendering
            support_email
                An help contact address
            upload_form
                The :class:`~mediacore.forms.uploader.UploadForm` instance
            form_values
                ``dict`` form values, if any

        """
        support_emails = request.settings['email_support_requests']
        support_emails = email.parse_email_string(support_emails)
        support_email = support_emails and support_emails[0] or None

        return dict(
            legal_wording = request.settings['wording_user_uploads'],
            support_email = support_email,
            upload_form = upload_form,
            form_values = kwargs,
        )

    @expose('json', request_method='POST')
    @validate(upload_form)
    @autocommit
    @observable(events.UploadController.submit_async)
    def submit_async(self, **kwargs):
        """Ajax form validation and/or submission.

        This is the save handler for :class:`~mediacore.forms.media.UploadForm`.

        When ajax is enabled this action is called for each field as the user
        fills them in. Although the entire form is validated, the JS only
        provides the value of one field at a time,

        :param validate: A JSON list of field names to check for validation
        :parma \*\*kwargs: One or more form field values.
        :rtype: JSON dict
        :returns:
            :When validating one or more fields:

            valid
                bool
            err
                A dict of error messages keyed by the field names

            :When saving an upload:

            success
                bool
            redirect
                If valid, the redirect url for the upload successful page.

        """
        if 'validate' in kwargs:
            # we're just validating the fields. no need to worry.
            fields = json.loads(kwargs['validate'])
            err = {}
            for field in fields:
                if field in tmpl_context.form_errors:
                    err[field] = tmpl_context.form_errors[field]

            data = dict(
                valid = len(err) == 0,
                err = err
            )
        else:
            # We're actually supposed to save the fields. Let's do it.
            if len(tmpl_context.form_errors) != 0:
                # if the form wasn't valid, return failure
                tmpl_context.form_errors['success'] = False
                data = tmpl_context.form_errors
            else:
                # else actually save it!
                kwargs.setdefault('name')

                apply_yourname = kwargs['name']
                apply_email = kwargs['email']
                apply_title = kwargs['title']
                apply_description = kwargs['description']
                apply_tags = None
                apply_categories = None
                apply_file = kwargs['file']
                apply_url = kwargs['url']

                if request.settings.get('create_accounts_on_upload', False):
                    # Figure out if the user is already here
                    user = User.by_email_address(kwargs['email'])
                    if user:
                        apply_yourname = user.display_name
                    else:
                        # get the RestrictedGroup group that we need (and create it if it's not already there)
                        restricted_group_name = request.settings.get('restricted_permissions_group')
                        restricted_group = DBSession.query(Group).filter(Group.group_name.in_([restricted_group_name])).first()
                        if not restricted_group:
                            make_new_group = Group(name=restricted_group_name, display_name=restricted_group_name)
                            DBSession.add(make_new_group)
                            DBSession.flush()
                            # get the group we just created
                            restricted_group = DBSession.query(Group).filter(Group.group_name.in_([restricted_group_name])).first()

                        # Create a new user using the model
                        user = User()
                        user_email = kwargs['email']
                        username_template = request.settings.get('create_account_username')
                        if not username_template:
                            username_template = '{email}'
                        user_name = username_template.format(email=user_email, handle=user_email[:user_email.index('@')])
                        builtin_editor_group = DBSession.query(Group).filter(Group.group_id.in_([2])).first()
                        defaults = dict(
                            user_name = user_name,
                            email_address = user_email,
                            display_name = kwargs['name'],
                            created = datetime.datetime.now(),
                            groups = [restricted_group, builtin_editor_group]
                            )
                        for key, value in defaults.items():
                            setattr(user, key, value)
                        user.password = u'changeme'
                        DBSession.add(user)
                        DBSession.flush()

                media_obj = self.save_media_obj(
                    apply_yourname, apply_email,
                    apply_title, apply_description,
                    apply_tags, apply_categories, apply_file, apply_url,
                )

                email.send_media_notification(media_obj)
                data = dict(
                    success = True,
                    redirect = url_for(action='success')
                )

        return data

    @expose(request_method='POST')
    @validate(upload_form, error_handler=index)
    @autocommit
    @observable(events.UploadController.submit)
    def submit(self, **kwargs):
        """
        """
        kwargs.setdefault('name')

        # Save the media_obj!
        media_obj = self.save_media_obj(
            kwargs['name'], kwargs['email'],
            kwargs['title'], kwargs['description'],
            None, kwargs['file'], kwargs['url'],
        )
        email.send_media_notification(media_obj)

        # Redirect to success page!
        redirect(action='success')

    @expose('upload/success.html')
    @observable(events.UploadController.success)
    def success(self, **kwargs):
        return dict()

    @expose('upload/failure.html')
    @observable(events.UploadController.failure)
    def failure(self, **kwargs):
        return dict()

    def save_media_obj(self, name, email, title, description, tags, categories, uploaded_file, url):
        # create our media object as a status-less placeholder initially
        media_obj = Media()
        media_obj.author = Author(name, email)
        media_obj.title = title
        media_obj.slug = get_available_slug(Media, title)
        media_obj.description = description
        if request.settings['wording_display_administrative_notes']:
            media_obj.notes = request.settings['wording_administrative_notes']
        media_obj.set_tags(tags)
        if categories:
            media_obj.set_categories(categories)

        # Give the Media object an ID.
        DBSession.add(media_obj)
        DBSession.flush()

        # Create a MediaFile object, add it to the media_obj, and store the file permanently.
        media_file = add_new_media_file(media_obj, file=uploaded_file, url=url)

        # The thumbs may have been created already by add_new_media_file
        if not has_thumbs(media_obj):
            create_default_thumbs_for(media_obj)

        media_obj.update_status()
        DBSession.flush()

        return media_obj
