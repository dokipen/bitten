from popen2 import Popen3

def make(basedir, target='all'):
    """Execute a Makefile target."""
    cmdline = 'make %s' % target
    pipe = Popen3(cmdline, capturestderr=True) # FIXME: Windows compatibility
    while True:
        retval = pipe.poll()
        if retval != -1:
            break
        line = pipe.fromchild.readline()
        if line:
            print '[make] %s' % line.rstrip()
        line = pipe.childerr.readline()
        if line:
            print '[make] %s' % line.rstrip()
    if retval != 0:
        raise BuildError, "Executing distutils failed (%s)" % retval
