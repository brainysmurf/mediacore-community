# This file is a part of MediaDrop (http://www.mediadrop.net),
# Copyright 2009-2013 MediaDrop contributors
# For the exact contribution history, see the git revision log.
# The source code contained in this file is licensed under the GPLv3 or
# (at your option) any later version.
# See LICENSE.txt in the main project directory, for more information.

from operator import itemgetter

from babel.core import Locale
from pylons import request
from tw.forms import RadioButtonList, SingleSelectField
from tw.forms.fields import CheckBox
from tw.forms.validators import (Bool, FieldStorageUploadConverter,
    Int, OneOf, Regex, StringBool)

from mediacore.forms import (FileField, ListFieldSet, ListForm,
    SubmitButton, TextArea, TextField, XHTMLTextArea,
    email_validator, email_list_validator)
from mediacore.forms.admin.categories import category_options
from mediacore.lib.i18n import N_, _, get_available_locales
from mediacore.plugin import events
from mediacore.model.settings import insert_settings

from mediacore.model.settings import insert_settings
from mediacore.model import Category

comments_enable_disable = lambda: (
    ('builtin', _("Built-in comments")),
    ('facebook', _('Facebook comments (requires a Facebook application ID)')),
    ('disabled', _('Disable comments')),
)
comments_enable_validator = OneOf(('builtin', 'facebook', 'disabled'))

title_options = lambda: (
    ('prepend', _('Prepend')),
    ('append', _('Append')),
)
rich_text_editors = lambda: (
    ('plain', _('Plain <textarea> fields (0kB)')),
    ('tinymce', _('Enable TinyMCE for <textarea> fields accepting XHTML (281kB)')),
)
rich_text_editors_validator = OneOf(('plain', 'tinymce'))
navbar_colors = lambda: (
    ('brown', _('Brown')),
    ('blue', _('Blue')),
    ('green', _('Green')),
    ('tan', _('Tan')),
    ('white', _('White')),
    ('purple', _('Purple')),
    ('black', _('Black')),
)
imap_options = lambda: (
    ('imapplain', _("imap plaintext")),
    ('imapcert', _("imap certificate")),
    ('imapssl', _("imap ssl")),
)

hex_validation_regex = "^#\w{3,6}$"
# End Appearance Settings #

def languages():
    # Note the extra space between English and [en]. This makes it sort above
    # the other translations of english, but is invisible to the user.
    result = [('en', u'English  [en]')]
    for name in get_available_locales():
        locale = Locale.parse(name)
        lang = locale.languages[locale.language].capitalize()
        if locale.territory:
            lang += u' (%s)' % locale.territories[locale.territory]
        else:
            lang += u' '
        lang += u' [%s]' % locale
        result.append((name, lang))
    result.sort(key=itemgetter(1))
    return result


def boolean_radiobuttonlist(name, **kwargs):
    return RadioButtonList(
        name,
        options=lambda: ((True, _('Yes')), (False, _('No'))),
        validator=StringBool,
        **kwargs
    )

class MediaCoreSettingsForm(ListForm):    
    def __init__(self, *args, **kwargs):
        super(ListForm, self).__init__(*args, **kwargs)
        self.init_values = []
        self.walk_fields(self.fields)
        if self.init_values:
            insert_settings(self.init_values)

    def walk_fields(self, fields):
        """ introspect fields and put append into self.defaults along the way """
        for field in fields:
            if hasattr(field, 'children') and field.children:
                # any field with 'children' is a placeholder, recurse
                if callable(field.children):
                    self.walk_fields(field.children())
                else:
                    self.walk_fields(field.children)
            else:
                if not field.name:
                    continue
                try:
                    prefix, key = field.name.split('.')
                except ValueError:
                    key = field.name
                if hasattr(field, 'init_value') and not request.settings.get(key):
                    # This field indicates it has a init_value and it's not in the database yet
                    self.init_values.append( (key, field.init_value) )
            
class NotificationsForm(MediaCoreSettingsForm):
    template = 'admin/box-form.html'
    id = 'settings-form'
    css_class = 'form'
    submit_text = None
    
    event = events.Admin.Settings.NotificationsForm
    
    fields = [
        ListFieldSet('email', suppress_label=True, legend=N_('Email Notifications:'), css_classes=['details_fieldset'], children=[
            TextField('email_media_uploaded', validator=email_list_validator, label_text=N_('Media Uploaded'), maxlength=255),
            CheckBox('email_media_uploaded_user', validator=Bool(if_missing=''), label_text=N_('To Uploader'), css_classes=['checkbox-left', 'checkbox-inline-help'], init_value=False),
            TextField('email_comment_posted', validator=email_list_validator, label_text=N_('Comment Posted'), maxlength=255),
            TextField('email_support_requests', validator=email_list_validator, label_text=N_('Support Requested'), maxlength=255),
            TextField('email_send_from', validator=email_validator, label_text=N_('Send Emails From'), maxlength=255),
        ]),
        SubmitButton('save', default=N_('Save'), css_classes=['btn', 'btn-save', 'blue', 'f-rgt']),
    ]


class PopularityForm(MediaCoreSettingsForm):
    template = 'admin/box-form.html'
    id = 'settings-form'
    css_class = 'form'
    submit_text = None
    
    event = events.Admin.Settings.PopularityForm
    
    fields = [
        ListFieldSet('popularity',
            suppress_label=True,
            css_classes=['details_fieldset'],
            legend=N_('Popularity Algorithm Variables:'),
            children=[
                TextField('popularity_decay_exponent', validator=Int(not_empty=True, min=1), label_text=N_('Decay Exponent')),
                TextField('popularity_decay_lifetime', validator=Int(not_empty=True, min=1), label_text=N_('Decay Lifetime')),
            ]
        ),
        SubmitButton('save', default=N_('Save'), css_classes=['btn', 'btn-save', 'blue', 'f-rgt']),
    ]

class MegaByteValidator(Int):
    """
    Integer Validator that accepts megabytes and translates to bytes.
    """
    def _to_python(self, value, state=None):
        try:
            value = int(value) * 1024 ** 2
        except ValueError:
            pass
        return super(MegaByteValidator, self)._to_python(value, state)

    def _from_python(self, value, state):
        try:
            value = int(value) / 1024 ** 4
        except ValueError:
            pass
        return super(MegaByteValidator, self)._from_python(value, state)

class LegalDomainsValidator(Regex):
    regex = r"^[a-zA-Z_0-9\-\., ]*$"

class UploadForm(MediaCoreSettingsForm):
    template = 'admin/box-form.html'
    id = 'settings-form'
    css_class = 'form'
    submit_text = None
    
    event = events.Admin.Settings.UploadForm
    
    fields = [
        TextField('max_upload_size', label_text=N_('Max. allowed upload file size in megabytes'), validator=MegaByteValidator(not_empty=True, min=0)),
        ListFieldSet('category_defaults', suppress_label=True,
                     legend=N_('Automatically assign default category:'),
                     css_classes=['details_fieldset'], children=[
            CheckBox('upload_assign_default_category_enabled', label_text=N_('Enabled'), css_classes=['checkbox-left'],
                     validator=Bool(if_missing=''), init_value=False),
            SingleSelectField('upload_default_category',
                     label_text=N_('Default Category'),
                     options=lambda : ["-" * depth + cat.name for cat, depth in Category.query.order_by(Category.name).populated_tree().traverse()],init_value='')
                     ]),
        ListFieldSet('restrict_domains', suppress_label=True,
                     legend=N_('User upload requires email address from specified domain(s):'),
                     css_classes=['details_fieldset'], children=[
            CheckBox('restrict_domains_enabled', label_text=N_('Enabled'), css_classes=['checkbox-left', 'checkbox-inline-help'],
                     validator=Bool(if_missing=''), init_value=False),
            CheckBox('restrict_single_domain_mode', label_text=N_('Single Domain Mode'), help_text=N_("(User can enter just the handle)"),
                     css_classes=['checkbox-left', 'checkbox-inline-help'],
                     validator=Bool(if_missing=''), init_value=False),
            TextField('handle_regexp_pattern', label_text=N_('Handle regexp pattern'), validator=None, init_value=''),
            TextField('illegal_domain_message', label_text=N_('Invalid domain message'),
                      validator=None, init_value='Your email has to be from the specified domain(s).'),
            TextField('illegal_handle_message', label_text=N_('Invalid handle message'),
                      validator=None, init_value='This email address is not a valid email for this domain.'),
            TextField('upload_empty_message', label_text=N_('Email empty message'),
                      validator=None, init_value="You've gotta have an email!"),
            TextArea('legal_domains', label_text=N_('Domains'), validator=LegalDomainsValidator(),
                     help_text=N_(u'Use commas to delineate multiple domains'), init_value=""),
            
            ]),
        ListFieldSet('requires_confirmation', suppress_label=True,
                     legend=N_('Create accounts on first upload with restricted permissions:'),
                     css_classes=['details_fieldset'], children=[
            CheckBox('create_accounts_on_upload', label_text=N_('Enabled'), css_classes=['checkbox-left'],
                     validator=Bool(if_missing=''), init_value=False),
            TextField('create_account_username', label_text=N_('Username'), validator=None,
                      help_text=N_(u'{email} {handle}'), init_value="{email}"),
            TextField('restricted_permissions_group', label_text=N_('Assigned Group'), validator=None, disabled=True,
                      help_text=lambda : N_(u'Users in the "{}" group only have permission to review and publish their own uploads. Users can be promoted by re-assignment in the "Users" settings. The name of this group cannot be changed to ensure functionality.'.format(request.settings.get('restricted_permissions_group', 'RestrictedGroup'))), init_value='RestrictedGroup'),
            TextArea('please_confirm_message', label_text=N_('Please confirm message'), validator=None,
                      help_text=N_(u'{confirmation_url} {sitename} {yourname} {email} {username} {email_send_from}'),
                      init_value = 'Greetings {yourname},\n\nSomeone (probably you) has recently uploaded an item onto {sitename}.\n\nPlease confirm this action and activate your account by clicking the link:\n\n{confirmation_url}\n\nYour new account will be activated and a subsequent email will follow.\n\nIf you have not uploaded anything, please ignore this notice.\n\nRegards,\n{site_name} Admin\n{email_send_from}'),
            TextArea('confirmed_message', label_text=N_('Confirmed message'), validator=None,
                      help_text=N_(u'{sitename} {yourname} {email} {username} {email_send_from}'),
                      init_value='Thank you for confirming your {sitename} account.\n\nYour account details are as follows:\n\nUsername: {username}\n\nYou will be prompted to enter a new password if you haven\'t changed it already.\n\nSincerely,\n{sitename} Admin{email_send_from}'),
            ]),
        ListFieldSet('upload_form_prompts', suppress_label=True,
                     legend=N_('Upload form prompts and help text:'),
                     css_classes=['details_fieldset'], children=[
            TextField('text_of_name_prompt', label_text=N_('"Your name"'), validator=None, init_value="Your name:"),
            TextField('text_of_name_help', label_text=N_('After ?'), validator=None, init_value=""),
            TextField('text_of_email_prompt', label_text=N_('"Email"'), validator=None, init_value="Your email:"),
            TextField('text_of_email_help', label_text=N_('After ?'), validator=None, init_value="(will never be published)"),
            TextField('text_of_title_prompt', label_text=N_('"Title"'), validator=None, init_value="Title:"),
            TextField('text_of_title_help', label_text=N_('After ?'), validator=None, init_value=""),
            TextField('text_of_description_prompt', label_text=N_('"Description"'), validator=None, init_value="Description:"),
            TextField('text_of_description_help', label_text=N_('After ?'), validator=None, init_value=""),
            ]),
        ListFieldSet('legal_wording', suppress_label=True, legend=N_('Legal Wording:'), css_classes=['details_fieldset'], children=[
            XHTMLTextArea('wording_user_uploads', label_text=N_('User Uploads'), attrs=dict(rows=15, cols=25),
                          help_text=N_(u'{sitename} {yourname} {email} {username}')),
        ]),

        SubmitButton('save', default=N_('Save'), css_classes=['btn', 'btn-save', 'blue', 'f-rgt']),
    ]

class AnalyticsForm(MediaCoreSettingsForm):
    template = 'admin/box-form.html'
    id = 'settings-form'
    css_class = 'form'
    submit_text = None
    
    event = events.Admin.Settings.AnalyticsForm
    
    fields = [
        ListFieldSet('google', suppress_label=True, legend=N_('Google Analytics Details:'), css_classes=['details_fieldset'], children=[
            TextField('google_analytics_uacct', maxlength=255, label_text=N_('Tracking Code')),
        ]),
        SubmitButton('save', default=N_('Save'), css_classes=['btn', 'btn-save', 'blue', 'f-rgt']),
    ]

class SiteMapsForm(MediaCoreSettingsForm):
    template = 'admin/box-form.html'
    id = 'settings-form'
    css_class = 'form'
    submit_text = None
    
    event = events.Admin.Settings.SiteMapsForm
    
    fields = [
        ListFieldSet('rss', suppress_label=True,
            legend='',
            css_classes=['details_fieldset'],
            children=[
                CheckBox('sitemaps_display',
                    css_classes=['checkbox-left'],
                    label_text=N_('Site Maps'),
                    validator=Bool(if_missing='')),
                CheckBox('rss_display',
                    css_classes=['checkbox-left'],
                    label_text=N_('RSS Feeds'),
                    validator=Bool(if_missing='')),
            ]
        ),
        ListFieldSet('feeds',
            suppress_label=True,
            css_classes=['details_fieldset'],
            legend=N_('RSS Feed Defaults:'),
            children=[
                TextField(u'default_feed_results', validator=Int(not_empty=True, min=1, if_missing=30), 
                    label_text=N_(u'number of items'),
                    help_text=N_(u'The number of items in the feed can be overriden per request '
                                 U'if you add "?limit=X" to the feed URL. If the "limit" parameter '
                                 u'is absent, the default above is used.'),
                ),
            ]
        ),
        SubmitButton('save', default=N_('Save'), css_classes=['btn', 'btn-save', 'blue', 'f-rgt']),
    ]

class GeneralForm(MediaCoreSettingsForm):
    template = 'admin/box-form.html'
    id = 'settings-form'
    css_class = 'form'
    submit_text = None
    
    event = events.Admin.Settings.GeneralForm
    
    fields = [
        ListFieldSet('general', suppress_label=True, legend=N_('General Settings:'), css_classes=['details_fieldset'], children=[
            TextField('general_site_name', maxlength=255,
                label_text=N_('Site Name')),
            SingleSelectField('general_site_title_display_order',
                label_text=N_('Display Site Name'),
                options=title_options,
            ),
            SingleSelectField('primary_language',
                label_text=N_('Default Language'), # TODO v0.9.1: Change to 'Primary Language'
                options=languages,
            ),
            SingleSelectField('featured_category',
                label_text=N_('Featured Category'),
                options=category_options,
                validator=Int(),
            ),
            RadioButtonList('rich_text_editor',
                label_text=N_('Rich Text Editing'),
                options=rich_text_editors,
                validator=rich_text_editors_validator,
            ),
        ]),
        ListFieldSet('imap_authentication', suppress_label=True, legend=N_('Use imap to authenticate users:'),
                     css_classes=['details_fieldset'], children=[
            CheckBox('imap_enabled',
                label_text=N_('Enabled'),
                help_text=N_('(Accounts will be visible in "Users" after they successfully log in)'),
                css_classes=['checkbox-inline-help'],
                validator=Bool(if_missing=''), init_value=False),
            TextField('imap_host', maxlength=255, label_text=N_('Domain'), init_value=''),
            SingleSelectField('imap_option_select',
                label_text=N_('imap'),
                options=imap_options, init_value='')
                ]),
        ListFieldSet('ldap_authentication', suppress_label=True, legend=N_('Use ldap to authenticate users:'),
                     css_classes=['details_fieldset'], children=[
            CheckBox('ldap_enabled',
                label_text=N_('Enabled'),
                help_text=N_('(Accounts will be visible in "Users" after they successfully log in)'),
                css_classes=['checkbox-inline-help'],
                validator=Bool(if_missing=''), init_value=False),
            TextField('ldap_host', maxlength=255, label_text=N_('Domain'), init_value='localhost'),
            TextField('ldap_ou', maxlength=255, label_text=N_('ou phrase'), init_value='ou=?'),
            TextField('ldap_dc', maxlength=255, label_text=N_('dc phrase'), init_value='dc=?,dc=?'),
            TextField('ldap_cn', maxlength=255, label_text=N_('"cn" word'), init_value='cn')]),
        ListFieldSet('site_vocabulary', suppress_label=True,
                     legend=N_('Your site\'s vocabulary regarding Podcasts:'),
                     css_classes=['details_fieldset'], children=[
            TextField('vocabulary_podcasts_plural', maxlength=255,
                label_text=N_('"Podcasts"'), init_value="Podcasts"),
            TextField('vocabulary_podcasts_singular', maxlength=255,
                label_text=N_('"Podcast"'), init_value="Podcast"),
            TextField('vocabulary_episodes_plural', maxlength=255,
                label_text=N_('"Episodes"'), init_value="Episodes"),
            TextField('vocabulary_episodes_singular', maxlength=255,
                label_text=N_('"Episode"'), init_value="Episode"),
            ]),
        SubmitButton('save', default=N_('Save'), css_classes=['btn', 'btn-save', 'blue', 'f-rgt']),
    ]

class CommentsForm(MediaCoreSettingsForm):
    template = 'admin/box-form.html'
    id = 'settings-form'
    css_class = 'form'
    submit_text = None
    
    event = events.Admin.Settings.CommentsForm
    
    fields = [
       RadioButtonList('comments_engine',
            label_text=N_('Comment Engine'),
            options=comments_enable_disable,
            validator=comments_enable_validator,
        ),
        ListFieldSet('builtin', suppress_label=True, legend=N_('Built-in Comments:'), css_classes=['details_fieldset'], children=[

            CheckBox('req_comment_approval',
                label_text=N_('Moderation'),
                help_text=N_('Require comments to be approved by an admin'),
                css_classes=['checkbox-inline-help'],
                validator=Bool(if_missing='')),
            TextField('akismet_key', label_text=N_('Akismet Key')),
            TextField('akismet_url', label_text=N_('Akismet URL')),
            TextArea('vulgarity_filtered_words', label_text=N_('Filtered Words'),
                attrs=dict(rows=3, cols=15),
                help_text=N_('Enter words to be filtered separated by a comma.')),
        ]),
        ListFieldSet('facebook', suppress_label=True, legend=N_('Facebook Comments:'), css_classes=['details_fieldset'], children=[
            TextField('facebook_appid', label_text=N_('Application ID'),
                help_text=N_('See: https://developers.facebook.com/apps')),
        ]),
        SubmitButton('save', default=N_('Save'), css_classes=['btn', 'btn-save', 'blue', 'f-rgt']),
    ]

class APIForm(MediaCoreSettingsForm):
    template = 'admin/box-form.html'
    id = 'settings-form'
    css_class = 'form'
    submit_text = None
    
    event = events.Admin.Settings.APIForm
    
    fields = [
        boolean_radiobuttonlist('api_secret_key_required', label_text=N_('Require a key to access the API')),
        ListFieldSet('key', suppress_label=True, legend=N_('API Key:'), css_classes=['details_fieldset'], children=[
            TextField('api_secret_key', label_text=N_('Access Key')),
        ]),
        ListFieldSet('prefs', suppress_label=True, legend=N_('API Settings:'), css_classes=['details_fieldset'], children=[
            TextField('api_media_max_results', label_text=N_('Max media results')),
            TextField('api_tree_max_depth', label_text=N_('Max tree depth')),
        ]),
        SubmitButton('save', default='Save', css_classes=['btn', 'btn-save', 'blue', 'f-rgt']),
    ]

class AppearanceForm(MediaCoreSettingsForm):
    template = 'admin/box-form.html'
    id = 'settings-form'
    css_class = 'form'
    submit_text = None
    
    event = events.Admin.Settings.AppearanceForm
    
    fields = [
        ListFieldSet('general', suppress_label=True, legend=N_('General'),
            css_classes=['details_fieldset'],
            children=[
                FileField('appearance_logo', label_text=N_('Logo'),
                    validator=FieldStorageUploadConverter(not_empty=False,
                        label_text=N_('Upload Logo')),
                    css_classes=[],
                    default=lambda: request.settings.get('appearance_logo', \
                                                             'logo.png'),
                    template='./admin/settings/appearance_input_field.html'),
                FileField('appearance_background_image', label_text=N_('Background Image'),
                    validator=FieldStorageUploadConverter(not_empty=False,
                        label_text=N_('Upload Background')),
                    css_classes=[],
                    default=lambda: request.settings.get('appearance_background_image', \
                                                             'bg_image.png'),
                    template='./admin/settings/appearance_input_field.html'),
                TextField('appearance_background_color', maxlength=255,
                    label_text=N_('Background color'),
                    validator=Regex(hex_validation_regex, strip=True)),
                TextField('appearance_link_color', maxlength=255,
                    label_text=N_('Link color'),
                    validator=Regex(hex_validation_regex, strip=True)),
                TextField('appearance_visited_link_color', maxlength=255,
                    label_text=N_('Visited Link color'),
                    validator=Regex(hex_validation_regex, strip=True)),
                TextField('appearance_text_color', maxlength=255,
                    validator=Regex(hex_validation_regex, strip=True),
                    label_text=N_('Text color')),
                TextField('appearance_heading_color', maxlength=255,
                    label_text=N_('Heading color'),
                    validator=Regex(hex_validation_regex, strip=True)),
                SingleSelectField('appearance_navigation_bar_color',
                    label_text=N_('Color Scheme'),
                    options=navbar_colors),
            ]
        ),
        ListFieldSet('options', suppress_label=True, legend=N_('Options'),
            css_classes=['details_fieldset'],
            children=[
                CheckBox('appearance_enable_cooliris',
                    css_classes=['checkbox-left'],
                    label_text=N_('Enable Cooliris on the Explore Page'),
                    help_text=N_('Cooliris support is deprecated and will be ' + \
                        'removed in the next major version of MediaDrop ' + \
                        'unless someone is interested in maintaining it.'),
                    validator=Bool(if_missing='')),
                CheckBox(u'appearance_display_login',
                    css_classes=['checkbox-left'],
                    label_text=N_('Display login link for all users'),
                    validator=Bool(if_missing='')),
                CheckBox('appearance_enable_featured_items',
                    label_text=N_('Enable Featured Items on the Explore Page'),
                    css_classes=['checkbox-left'],
                    validator=Bool(if_missing='')),
                CheckBox('appearance_enable_podcast_tab',
                    label_text=N_('Enable Podcast Tab'),
                    css_classes=['checkbox-left'],
                    validator=Bool(if_missing='')),
                CheckBox('appearance_enable_user_uploads',
                    label_text=N_('Enable User Uploads'),
                    css_classes=['checkbox-left'],
                    validator=Bool(if_missing='')),
                CheckBox('appearance_enable_login_button',
                    label_text=N_('Enable Login Button'),
                    css_classes=['checkbox-left'],
                    validator=Bool(if_missing=''), init_value=True),
                CheckBox('appearance_enable_widescreen_view',
                    label_text=N_('Enable widescreen media player by default'),
                    css_classes=['checkbox-left'],
                    validator=Bool(if_missing='')),
                CheckBox('appearance_display_logo',
                    label_text=N_('Display Logo'),
                    css_classes=['checkbox-left'],
                    validator=Bool(if_missing='')),
                CheckBox('appearance_display_background_image',
                    label_text=N_('Display Background Image'),
                    css_classes=['checkbox-left'],
                    validator=Bool(if_missing='')),
                CheckBox('appearance_display_mediadrop_footer',
                    label_text=N_('Display MediaDrop Footer'),
                    css_classes=['checkbox-left'],
                    validator=Bool(if_missing='')),
                CheckBox('appearance_display_mediadrop_credits',
                    label_text=N_('Display MediaDrop Credits in Footer'),
                    css_classes=['checkbox-left'],
                    validator=Bool(if_missing='')),
            ],
            template='./admin/settings/appearance_list_fieldset.html',
        ),
        ListFieldSet('player', suppress_label=True, legend=N_('Player Menu Options'),
            css_classes=['details_fieldset'],
            children=[
                CheckBox('appearance_show_download',
                    css_classes=['checkbox-left'],
                    label_text=N_('Enable Download button on player menu bar.'),
                    validator=Bool(if_missing='')),
                CheckBox('appearance_show_share',
                    css_classes=['checkbox-left'],
                    label_text=N_('Enable Share button on player menu bar.'),
                    validator=Bool(if_missing='')),
                CheckBox('appearance_show_embed',
                    css_classes=['checkbox-left'],
                    label_text=N_('Enable Embed button on player menu bar.'),
                    validator=Bool(if_missing='')),
                CheckBox('appearance_show_widescreen',
                    css_classes=['checkbox-left'],
                    label_text=N_('Enable Widescreen toggle button on player menu bar.'),
                    validator=Bool(if_missing='')),
                CheckBox('appearance_show_popout',
                    css_classes=['checkbox-left'],
                    label_text=N_('Enable Popout button on player menu bar.'),
                    validator=Bool(if_missing='')),
                CheckBox('appearance_show_like',
                    css_classes=['checkbox-left'],
                    label_text=N_('Enable Like button on player menu bar.'),
                    validator=Bool(if_missing='')),
                CheckBox('appearance_show_dislike',
                    css_classes=['checkbox-left'],
                    label_text=N_('Enable Dislike button on player menu bar.'),
                    validator=Bool(if_missing='')),
            ],
            template='./admin/settings/appearance_list_fieldset.html',
        ),
        ListFieldSet('advanced', suppress_label=True, legend=N_('Advanced'),
            css_classes=['details_fieldset'],
            children=[
                TextArea('appearance_custom_css',
                    label_text=N_('Custom CSS'),
                    attrs=dict(rows=15, cols=25)),
                TextArea('appearance_custom_header_html',
                    label_text=N_('Custom Header HTML'),
                    attrs=dict(rows=15, cols=25)),
                TextArea('appearance_custom_footer_html',
                    label_text=N_('Custom Footer HTML'),
                    attrs=dict(rows=15, cols=25)),
                TextArea('appearance_custom_head_tags',
                    label_text=N_('Custom <head> Tags'),
                    help_text=N_('These HTML tags are inserted into the HTML '
                        '<head> section. Bad input can cause ugly rendering of '
                        'your site. You can always restore your page by '
                        'the box above.'),
                    attrs=dict(rows=15, cols=25)),
            ],
        ),
        SubmitButton('save', default=N_('Save'), css_classes=['btn', 'btn-save', 'blue', 'f-rgt']),
        SubmitButton('reset', default=N_('Reset to Defaults'),
            css_classes=['btn', 'btn-cancel', 'reset-confirm']),
    ]

class AdvertisingForm(MediaCoreSettingsForm):
    template = 'admin/box-form.html'
    id = 'settings-form'
    css_class = 'form'
    submit_text = None
    
    event = events.Admin.Settings.AdvertisingForm
    
    fields = [
        ListFieldSet('advanced', suppress_label=True, legend='',
            css_classes=['details_fieldset'],
            children=[
                TextArea('advertising_banner_html',
                    label_text=N_('Banner HTML'),
                    attrs=dict(rows=15, cols=25)),
                TextArea('advertising_sidebar_html',
                    label_text=N_('Sidebar HTML'),
                    attrs=dict(rows=15, cols=25)),
            ],
        ),
        SubmitButton('save', default=N_('Save'), css_classes=['btn', 'btn-save', 'blue', 'f-rgt']),
    ]


