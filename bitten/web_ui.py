from __future__ import generators
import re

from trac.core import *
from trac.web.chrome import INavigationContributor
from trac.web.main import AbstractView, IRequestHandler


class BuildModule(AbstractView):

    implements(INavigationContributor, IRequestHandler)

    build_cs = """
<?cs include:"header.cs" ?>
<div id="main">
 <div id="ctxtnav" class="nav"></div>
  <h1>Build Status</h1>
 <div id="content"></div>
</div>
<?cs include:"footer.cs" ?>
"""

    # INavigationContributor methods

    def get_active_navigation_item(self, req):
        return 'build'

    def get_navigation_items(self, req):
        yield 'mainnav', 'build', '<a href="%s">Builds</a>' \
                                  % self.env.href.build()

    # IRequestHandler methods

    def match_request(self, req):
        match = re.match(r'/build(:?/(\w+))?', req.path_info)
        if match:
            if match.group(1):
                req.args['id'] = match.group(1)
            return True

    def process_request(self, req):
        return req.hdf.parse(self.build_cs), None
