from distutils.core import setup, Command
from unittest import TextTestRunner


class test(Command):
    description = "Runs the unit tests"
    user_options = [('test-suite=', 's', "Name of the unittest suite to run")]

    def initialize_options(self):
        self.test_suite = None

    def finalize_options(self):
        pass

    def run(self):
        print 'Hey yo'
        print self.test_suite
        suite = __import__(self.test_suite, locals(), globals())
        runner = unittest.TextTestRunner()
        TextTestRunner.run(suite)


setup(name='bitten', version='1.0',
      packages=['bitten', 'bitten.general', 'bitten.python'],
      cmdclass={'test': test})
