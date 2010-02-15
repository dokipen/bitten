#-*- coding: utf-8 -*-
#
# Copyright (C) 2007 Ole Trenner, <ole@jayotee.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

from trac.core import *
from trac.web.chrome import Chrome

from genshi.template import NewTextTemplate, TemplateLoader

from announcer.api import AnnouncementSystem, AnnouncementEvent
from announcer.api import IAnnouncementFormatter, IAnnouncementSubscriber
from announcer.api import IAnnouncementPreferenceProvider
from announcer.distributors.mail import IAnnouncementEmailDecorator
from announcer.util.mail import set_header, next_decorator

from bitten.api import IBuildListener
from bitten.model import Build, BuildStep, BuildLog


class BittenAnnouncedEvent(AnnouncementEvent):
    def __init__(self, build, category):
        AnnouncementEvent.__init__(self, 'bitten', category, build)

class BittenAnnouncement(Component):
    """Send announcements on build status."""

    implements(
        IBuildListener,
        IAnnouncementSubscriber, 
        IAnnouncementFormatter,
        IAnnouncementEmailDecorator,
        IAnnouncementPreferenceProvider
    )

    readable_states = {
        Build.SUCCESS: 'Successful',
        Build.FAILURE: 'Failed',
    }

    # IBuildListener interface
    def build_started(self, build):
        """build started"""
        self._notify(build, 'started')

    def build_aborted(self, build):
        """build aborted"""
        self._notify(build, 'aborted')

    def build_completed(self, build):
        """build completed"""
        self._notify(build, 'completed')

    # IAnnouncementSubscriber interface
    def subscriptions(self, event):
        if event.realm == 'bitten':
            if event.target.status in (Build.FAILURE, Build.SUCCESS):
                for subscriber in self._get_membership(event.target):
                    self.log.debug("BittenAnnouncementSubscriber added '%s " \
                            "(%s)'", subscriber[1], subscriber[2])
                    yield subscriber

    # IAnnouncementFormatter interface
    def styles(self, transport, realm):
        if realm == 'bitten':
            yield 'text/plain'

    def alternative_style_for(self, transport, realm, style):
        if realm == 'bitten' and style != 'text/plain':
            return 'text/plain'

    def format(self, transport, realm, style, event):
        if realm == 'bitten' and style == 'text/plain':
            return self._format_plaintext(event)

    # IAnnouncementEmailDecorator
    def decorate_message(self, event, message, decorates=None):
        if event.realm == "bitten":
            build_id = str(event.target.id)
            build_link = self._build_link(event.target)
            subject = '[%s Build] %s [%s] %s' % (
                self.readable_states.get(
                    event.target.status, 
                    event.target.status
                ),
                self.env.project_name,
                event.target.rev,
                event.target.config
            )
            set_header(message, 'X-Trac-Build-ID', build_id)
            set_header(message, 'X-Trac-Build-URL', build_link)
            set_header(message, 'Subject', subject) 
        return next_decorator(event, message, decorates)

    # IAnnouncementPreferenceProvider interface
    def get_announcement_preference_boxes(self, req):
        if req.authname == "anonymous" and 'email' not in req.session:
            return
        yield "bitten_subscription", "Bitten Subscription"

    def render_announcement_preference_box(self, req, panel):
        if req.method == "POST":
            if req.args.get('bitten_subscription', None):
                req.session['announcer_notify_bitten'] = '1'
            else:
                if 'announcer_notify_bitten' in sess:
                    del req.session['announcer_notify_bitten']
        notify = req.session.get('announcer_notify_bitten', None)
        return "prefs_announcer_bitten_subscription.html", dict(
            data=dict(
                announcer_notify_bitten=notify
            )
        )

    # private methods
    def _notify(self, build, category):
        self.log.info('BittenAnnouncedEventProducer invoked for build %r', build)
        self.log.debug('build status: %s', build.status)
        self.log.info('Creating announcement for build %r', build)
        try:
            announcer = AnnouncementSystem(self.env)
            announcer.send(BittenAnnouncedEvent(build, category))
        except Exception, e:
            self.log.exception("Failure creating announcement for build "
                               "%s: %s", build.id, e)

    def _get_membership(self, build):
        if not build:
            return
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
            SELECT sid, authenticated
              FROM session_attribute
             WHERE name='announcer_notify_bitten'
        """)
        for result in cursor.fetchall():
            if result[1] in (1, '1', True):
                authenticated = True
            else:
                authenticated = False
            yield ('email', result[0], authenticated, None)

    def _format_plaintext(self, event):
        failed_steps = BuildStep.select(self.env, build=event.target.id,
                                        status=BuildStep.FAILURE)
        change = self._get_changeset(event.target)
        data = {
            'build': {
                'id': event.target.id,
                'status': self.readable_states.get(
                    event.target.status, event.target.status
                ),
                'link': self._build_link(event.target),
                'config': event.target.config,
                'slave': event.target.slave,
                'failed_steps': [{
                    'name': step.name,
                    'description': step.description,
                    'errors': step.errors,
                    'log_messages': 
                       self._get_all_log_messages_for_step(event.target, step),
                } for step in failed_steps],
            },
            'change': {
                'rev': change.rev,
                'link': self.env.abs_href.changeset(change.rev),
                'author': change.author,
            },
            'project': {
                'name': self.env.project_name,
                'url': self.env.project_url or self.env.abs_href(),
                'descr': self.env.project_description
            }
        }
        chrome = Chrome(self.env)
        dirs = []
        for provider in chrome.template_providers:
            dirs += provider.get_templates_dirs()
        templates = TemplateLoader(dirs, variable_lookup='lenient')
        template = templates.load('bitten_announcement.txt', 
                cls=NewTextTemplate)
        if template:
            stream = template.generate(**data)
            output = stream.render('text')
        return output

    def _build_link(self, build):
        return self.env.abs_href.build(build.config, build.id)

    def _get_all_log_messages_for_step(self, build, step):
        messages = []
        for log in BuildLog.select(self.env, build=build.id,
                                   step=step.name):
            messages.extend(log.messages)
        return messages

    def _get_changeset(self, build):
        return self.env.get_repository().get_changeset(build.rev)

