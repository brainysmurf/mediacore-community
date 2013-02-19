# This file is a part of MediaCore CE (http://www.mediacorecommunity.org),
# Copyright 2009-2013 MediaCore Inc., Felix Schwarz and other contributors.
# For the exact contribution history, see the git revision log.
# The source code contained in this file is licensed under the GPLv3 or
# (at your option) any later version.
# See LICENSE.txt in the main project directory, for more information.

from pylons import request
from tw.api import WidgetsList
from tw.forms.validators import FieldStorageUploadConverter

from mediacore.lib.i18n import N_
from mediacore.forms import ListForm, TextField, TextArea, XHTMLTextArea, FileField, SubmitButton, email_validator
from mediacore.plugin import events
from tw.forms.validators import Email
from formencode.api import Invalid
import psycopg2
import re

validators = dict(
    description = XHTMLTextArea.validator(
        messages = {'empty': N_('There must be something to describe...')},
        not_empty = True,
    ),
    name = TextField.validator(
        messages = {'empty': N_("You've gotta have a name!")},
        not_empty = True,
    ),
    title = TextField.validator(
        messages = {'empty': N_("You've gotta have a title!")},
        not_empty = True,
    ),
    tags = TextField.validator(
        messages = {'empty': N_("At least pick one word!")},
        not_empty = True,
    ),
    url = TextField.validator(
        if_missing = None,
    ),
)

class UploadEmailValidator(Email):
    """
    Checks the legal domains as entered by user
    """
    def __init__(self, *args, **kwargs):
        self.restrict_domains = request.settings.get('restrict_domains_enabled', False)
        self.single_domain_mode = self.restrict_domains and request.settings.get('restrict_single_domain_mode', False)
        self.legal_domains = self.parse_domains()
        if not self.legal_domains:
            pass  # TODO: Some error here            
        self.dnet_connection = psycopg2.connect("host=dragonnet.ssis-suzhou.net dbname=moodle user=moodle")
        self.dnet_cursor = self.dnet_connection.cursor()
        super(UploadEmailValidator, self).__init__(
                       messages={'illegalDomain': N_(request.settings.get('illegal_domain_message') or 'Must be from the right domain.'),
                                 'illegalHandle': N_(request.settings.get('illegal_handle_message') or 'This is not a valid email at this domain.'),
                                 'noDragonNet': N_("This DragonNet name does not exist!"),
                                 'empty': N_(request.settings.get('upload_empty_message') or "You've gotta have an email!")}, *args, **kwargs)

    def parse_domains(self):
        """ Simple regexp parser with comma as delimiter """
        return re.split(r'[, ]*', request.settings.get('legal_domains') or u'')

    def validate_python(self, value, state):
        """ Adds domain checking by completely overriding """
        if not value:
            raise Invalid(self.message('empty', state), value, state)
        value = value.strip()
        splitted = value.split('@', 1)
        # Added this line:
        handle_regexp = request.settings.get('handle_regexp_pattern')

        try:
            username, domain=splitted
        except ValueError:
            # Added code
            if self.single_domain_mode:
                if handle_regexp and not re.match(handle_regexp, value):
                    raise Invalid(
                        self.message('illegalHandle', state, value=value),
                        value, state)
                else:
                    return
            # End added code
            else:
                raise Invalid(self.message('noAt', state), value, state)
        if not self.usernameRE.search(username):
            raise Invalid(
                self.message('badUsername', state, username=username),
                value, state)
        if not self.domainRE.search(domain):
            raise Invalid(
                self.message('badDomain', state, domain=domain),
                value, state)
        # Added code
        if self.restrict_domains and not domain in self.legal_domains:
            raise Invalid(
                self.message('illegalDomain', state, domain=domain),
                value, state)
        if handle_regexp and not re.match(handle_regexp, username):
            raise Invalid(
                self.message('illegalHandle', state, username=username),
                value, state) 
        exists = self.dnet_cursor.execute("select firstname, lastname from ssismdl_user where username = '{}'".format(user_name))
        if not exists:
            raise Invalid(
                self.message('noDragonNet', state, username=username),
                value, state)
        # End added code
        if self.resolve_domain:
            assert have_dns, "pyDNS should be available"
            global socket
            if socket is None:
                import socket
            try:
                answers = DNS.DnsRequest(domain, qtype='a',
                    timeout=self.resolve_timeout).req().answers
                if answers:
                    answers = DNS.DnsRequest(domain, qtype='mx',
                        timeout=self.resolve_timeout).req().answers
            except (socket.error, DNS.DNSError), e:
                raise Invalid(
                    self.message('socketError', state, error=e),
                    value, state)
            if not answers:
                raise Invalid(
                    self.message('domainDoesNotExist', state, domain=domain),
                    value, state)                

class UploadForm(ListForm):
    template = 'upload/form.html'
    id = 'upload-form'
    css_class = 'form'
    show_children_errors = False
    params = ['async_action']
    
    events = events.UploadForm
    
    class fields(WidgetsList):
        #file = FileField(validator=FieldStorageUploadConverter(if_missing=None, messages={'empty':N_('Oops! You forgot to enter a file.')}), label_text=N_('Upload:'), help_text="(Must be an mp4 or m4a file)")
        #name = TextField(validator=validators['name'], label_text=N_(request.settings.get('text_of_name_prompt') or 'Your Name:'), help_text=N_(request.settings.get('text_of_name_help') or ''), maxlength=50)
        email = TextField(validator=UploadEmailValidator(not_empty=True), label_text=N_(request.settings.get('text_of_email_prompt') or 'Your email:'), help_text=N_(request.settings.get('text_of_email_help') or ''), maxlength=255)
        title = TextField(validator=validators['title'], label_text=N_(request.settings.get('text_of_title_prompt') or 'Title:'), help_text=N_(request.settings.get('text_of_title_help') or ''), maxlength=255)
        tags = TextArea(validator=validators['tags'], label_text=N_(request.settings.get('text_of_tags_prompt') or 'Tags:'), help_text=N_(request.settings.get('text_of_tag_help') or '(one tag for each line)'), maxlength=255)
        description = TextField(validator=validators['description'], label_text=N_(request.settings.get('text_of_description_prompt') or 'Description:'), help_text=N_(request.settings.get('text_of_description_help') or ''), attrs=dict(rows=5, cols=25))
        #url = TextField(validator=validators['url'], label_text=N_('Add a YouTube, Vimeo or Google Video URL:'), maxlength=255)
        submit = SubmitButton(default=N_('Continue'), css_classes=['mcore-btn', 'btn-submit'])
