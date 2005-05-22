import os
import os.path
from elementtree import ElementTree

from trac.core import *


class ICommandExecutor(Interface):

    def get_name():
        """
        Return the name of the command as used in the XML file.
        """

    def execute(basedir, *attrs):
        """
        """


class IReportPreparator(Interface):

    def get_name():
        """
        Return the name of the command as used in the XML file.
        """

    def process(basedir, **attrs):
        """
        """


class RecipeExecutor(Component):

    commands = ExtensionPoint(ICommandExecutor)
    reporters = ExtensionPoint(IReportPreparator)

    def execute(self, filename='recipe.xml', basedir=os.getcwd()):
        path = os.path.join(basedir, filename)
        recipe = ElementTree.parse(path).getroot()
        for step in recipe:
            print '---> %s' % step.attrib['title']
            for element in step:
                if element.tag == 'reports':
                    for report in element:
                        reporter = self._get_reporter(report.tag)
                        reporter.execute(basedir, **report.attrib)
                else:
                    cmd = self._get_command(element.tag)
                    cmd.execute(basedir, **element.attrib)
            print

    def _get_command(self, name):
        for command in self.commands:
            if command.get_name() == name:
                return command
        raise Exception, "Unknown command <%s>" % name

    def _get_reporter(self, name):
        for report in self.reporters:
            if report.get_name() == name:
                return report
        raise Exception, "Unknown report <%s>" % name
