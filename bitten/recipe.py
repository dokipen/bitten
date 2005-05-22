import os
import os.path
from elementtree import ElementTree

from trac.core import *


class ICommandExecutor(Interface):

    def get_name():
        """
        Return the name of the command as used in the XML file.
        """

    def execute(basedir, **attrs):
        """
        """


class IReportProcessor(Interface):

    def get_name():
        """
        Return the name of the command as used in the XML file.
        """

    def process(basedir, **attrs):
        """
        """


class Recipe(object):

    def __init__(self, filename='recipe.xml', basedir=os.getcwd()):
        self.filename = filename
        self.basedir = basedir
        self.path = os.path.join(basedir, filename)
        self.tree = ElementTree.parse(self.path).getroot()

    description = property(fget=lambda self: self.tree.attrib['description'])


class RecipeExecutor(Component):

    command_executors = ExtensionPoint(ICommandExecutor)
    report_processors = ExtensionPoint(IReportProcessor)

    def execute(self, recipe):
        for step in recipe.tree:
            print '---> %s' % step.attrib['title']
            for element in step:
                if element.tag == 'reports':
                    for report in element:
                        reporter = self._get_report_processor(report.tag)
                        reporter.process(recipe.basedir, **report.attrib)
                else:
                    cmd = self._get_command_executor(element.tag)
                    cmd.execute(recipe.basedir, **element.attrib)
            print

    def _get_command_executor(self, name):
        for command_executor in self.command_executors:
            if command_executor.get_name() == name:
                return command_executor
        raise Exception, "Unknown command <%s>" % name

    def _get_report_processor(self, name):
        for report_processor in self.report_processors:
            if report_processor.get_name() == name:
                return report_processor
        raise Exception, "Unknown report type <%s>" % name
