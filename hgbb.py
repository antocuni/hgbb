# -*- coding: utf-8 -*-
"""
    hgbb
    ~~~~

    This extension provides simple access to some bitbucket features such as
    checkout via short URL schemes.

    Configuration values::

        [bb]
        username = your bitbucket username
        password = your bitbucket http password for http (optional)
        default_method = the default checkout method to use (http, ssh or https)

    Implemented URL Schemas:

    bb:repo
        clones your own "repo" repository, checkout via default method

    bb:username/repo
        clones the "repo" repository by username, checkout via default method

    bb+http:repo
        clones your own "repo" repository, checkout via http

    bb+http:username/repo
        clones the "repo" repository by username, checkout via http

    bb+ssh:repo
        clones your own "repo" repository, checkout via ssh

    bb+ssh:username/repo
        clones the "repo" repository by username, checkout via ssh

    :copyright: 2009, 2010 by Armin Ronacher, Georg Brandl.
    :license:
        This program is free software; you can redistribute it and/or modify it
        under the terms of the GNU General Public License as published by the
        Free Software Foundation; either version 2 of the License, or (at your
        option) any later version.

        This program is distributed in the hope that it will be useful, but
        WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
        General Public License for more details.

        You should have received a copy of the GNU General Public License along
        with this program; if not, write to the Free Software Foundation, Inc.,
        51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""

from mercurial import hg, commands, sshrepo, httprepo, util, error

import urllib
import urlparse
from time import sleep

from lxml.html import parse


def getusername(ui):
    """Return the bitbucket username or guess from the login name."""
    username = ui.config('bb', 'username', None)
    if username:
        return username
    import getpass
    return getpass.getuser()


class bbrepo(object):
    """Short URL to clone from or push to bitbucket."""

    def __init__(self, factory, url):
        self.factory = factory
        self.url = url

    def instance(self, ui, url, create):
        scheme, path = url.split(':', 1)
        if path.startswith('//'):
            path = path[2:]
        username = getusername(ui)
        if '/' not in path:
            path = username + '/' + path
        password = ui.config('bb', 'password', None)
        if password is not None:
            auth = '%s:%s@' % (username, password)
        else:
            auth = username + '@'
        formats = dict(
            path=path.rstrip('/') + '/',
            auth=auth
        )
        return self.factory(ui, self.url % formats, create)


class auto_bbrepo(object):
    def instance(self, ui, url, create):
        method = ui.config('bb', 'default_method', 'https')
        if method not in ('ssh', 'http', 'https'):
            raise util.Abort('Invalid config value for bb.default_method: %s'
                             % method)
        return hg.schemes['bb+' + method].instance(ui, url, create)


def bb_forks(ui, repo, **opts):
    reponame = opts.get('reponame')
    if not reponame:
        reponame = 'sphinx'
    if '/' not in reponame:
        reponame = '%s/%s' % (getusername(ui), reponame)
    ui.status('getting descendants list\n')
    fp = urllib.urlopen('http://bitbucket.org/%s/descendants' % reponame)
    try:
        tree = parse(fp)
    finally:
        fp.close()
    try:
        forklist = tree.findall('//div[@class="repos-all"]')[1]
        urls = [a.attrib['href'] for a in forklist.findall('div/a')]
    except Exception:
        raise util.Abort('scraping bitbucket page failed')
    forks = [(urlparse.urlsplit(url)[2][1:], url) for url in urls]
    # filter
    ignore = set(ui.configlist('bb', 'ignore_forks'))
    forks = [(name, url) for (name, url) in forks if name not in ignore]

    if opts.get('incoming'):
        for name, url in forks:
            ui.status('looking at bb+http:%s\n' % name)
            try:
                ui.quiet = True
                ui.pushbuffer()
                try:
                    commands.incoming(ui, repo, url, bundle='', template='\xff')
                finally:
                    ui.quiet = False
                    contents = ui.popbuffer()
            except error.RepoError, msg:
                ui.warn('Error: %s\n' % msg)
            finally:
                if contents:
                    number = contents.count('\xff')
                    if number:
                        ui.status('%d incoming changeset%s found\n' %
                                  (number, number > 1 and 's' or ''),
                                  label='status.modified')
                    ui.write(contents.replace('\xff', ''))
    else:
        for name, url in forks:
            ui.status('bb+http:%s\n' % name)
            #json = urllib.urlopen(
            #    'http://api.bitbucket.org/1.0/repositories/%s/' % name).read()


hg.schemes['bb'] = auto_bbrepo()
hg.schemes['bb+http'] = bbrepo(
    httprepo.instance, 'http://%(auth)sbitbucket.org/%(path)s')
hg.schemes['bb+https'] = bbrepo(
    httprepo.instance, 'https://%(auth)sbitbucket.org/%(path)s')
hg.schemes['bb+ssh'] = bbrepo(
    sshrepo.sshrepository, 'ssh://hg@bitbucket.org/%(path)s')

cmdtable = {
    'bbforks':
        (bb_forks,
         [('n', 'reponame', '',
           'name of the repo at bitbucket (else guessed from repo dir)'),
          ('i', 'incoming', None,
           'look for incoming changesets')
          ],
         'hg bbforks [-n reponame]')
}
