#-*- coding: utf-8 -*-
#
# Copyright (C) 2007 Ole Trenner, <ole@jayotee.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

from trac.core import Component, implements
from trac.web.chrome import ITemplateProvider
from trac.config import BoolOption
from trac.notification import NotifyEmail
from bitten.api import IBuildListener
from bitten.model import Build, BuildStep, BuildLog


class BittenNotify(Component):
    """Sends notifications on build status by mail."""
    implements(IBuildListener, ITemplateProvider)

    notify_on_failure = BoolOption('notification',
            'notify_on_failed_build', 'true',
            """Notify if bitten build fails.""")

    notify_on_success = BoolOption('notification',
            'notify_on_successful_build', 'false',
            """Notify if bitten build succeeds.""")

    def __init__(self):
        self.log.debug('Initializing BittenNotify plugin')

    def notify(self, build=None):
        self.log.info('BittenNotify invoked for build %r', build)
        self.log.debug('build status: %s', build.status)
        if not self._should_notify(build):
            return
        self.log.info('Sending notification for build %r', build)
        try:
            email = BuildNotifyEmail(self.env)
            email.notify(build)
        except Exception, e:
            self.log.exception("Failure sending notification for build "
                               "%s: %s", build.id, e)

    def _should_notify(self, build):
        if build.status == Build.FAILURE:
            return self.notify_on_failure
        elif build.status == Build.SUCCESS:
            return self.notify_on_success
        else:
            return False

    # IBuildListener methods

    def build_started(self, build):
        """build started"""
        self.notify(build)

    def build_aborted(self, build):
        """build aborted"""
        self.notify(build)

    def build_completed(self, build):
        """build completed"""
        self.notify(build)

    # ITemplateProvider methods

    def get_templates_dirs(self):
        """Return a list of directories containing the provided template
        files."""
        from pkg_resources import resource_filename
        return [resource_filename(__name__, 'templates')]

    def get_htdocs_dirs(self):
        """Return the absolute path of a directory containing additional
        static resources (such as images, style sheets, etc)."""
        return []


class BuildNotifyEmail(NotifyEmail):
    """Notification of failed builds."""

    readable_states = {
        Build.SUCCESS: 'Successful',
        Build.FAILURE: 'Failed',
    }
    template_name = 'bitten_notify_email.txt'
    from_email = 'bitten@localhost'

    def __init__(self, env):
        NotifyEmail.__init__(self, env)

    def notify(self, build):
        self.build = build
        self.data.update(self.template_data())
        subject = '[%s Build] %s [%s] %s' % (self.readable_states[build.status],
                                             self.env.project_name,
                                             self.build.rev,
                                             self.build.config)
        NotifyEmail.notify(self, self.build.id, subject)

    def get_recipients(self, resid):
        to = [self.get_author()]
        cc = []
        return (to, cc)

    def send(self, torcpts, ccrcpts):
        mime_headers = {
            'X-Trac-Build-ID': str(self.build.id),
            'X-Trac-Build-URL': self.build_link(),
        }
        NotifyEmail.send(self, torcpts, ccrcpts, mime_headers)

    def build_link(self):
        return self.env.abs_href.build(self.build.config, self.build.id)

    def template_data(self):
        failed_steps = BuildStep.select(self.env, build=self.build.id,
                                        status=BuildStep.FAILURE)
        change = self.get_changeset()
        return {
            'build': {
                'id': self.build.id,
                'status': self.readable_states[self.build.status],
                'link': self.build_link(),
                'config': self.build.config,
                'slave': self.build.slave,
                'failed_steps': [{
                    'name': step.name,
                    'description': step.description,
                    'errors': step.errors,
                    'log_messages': self.get_all_log_messages_for_step(step),
                } for step in failed_steps],
            },
            'change': {
                'rev': change.rev,
                'link': self.env.abs_href.changeset(change.rev),
                'author': change.author,
            },
        }

    def get_all_log_messages_for_step(self, step):
        messages = []
        for log in BuildLog.select(self.env, build=self.build.id,
                                   step=step.name):
            messages.extend(log.messages)
        return messages

    def get_changeset(self):
        return self.env.get_repository().get_changeset(self.build.rev)

    def get_author(self):
        return self.get_changeset().author
