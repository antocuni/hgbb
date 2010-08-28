# -*- coding: utf-8 -*-
#
# bitbucket.org mercurial extension
#
# Copyright (c) 2009, 2010 by Armin Ronacher, Georg Brandl.
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51 Franklin
# Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
"""convenient access to bitbucket.org repositories and features

This extension has two purposes:

- access bitbucket repositories via short URIs like ``bb:[name/]repo``
- conveniently do several bitbucket.org operations on the command line

Configuration::

    [bb]
    username = your bitbucket username
    password = your bitbucket http password for http (otherwise you'll be asked)
    default_method = the default checkout method to use (ssh, http or https)

There is one additional configuration value that makes sense only in
repository-specific configuration files::

    ignore_forks = comma-separated list of forks you'd like to ignore in bbforks

The forks are given by bitbucket repository names (``username/repo``).

Implemented URL schemas, usable instead of ``http://bitbucket.org/...``:

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
"""

from mercurial import hg, commands, sshrepo, httprepo, util, error

import os
import urllib
import urlparse

from lxml.html import parse


def getusername(ui):
    """Return the bitbucket username or guess from the login name."""
    username = ui.config('bb', 'username', None)
    if username:
        return username
    import getpass
    username = getpass.getuser()
    ui.status('using system user %r as username' % username)
    return username


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


def get_reponame(ui, repo, opts):
    reponame = opts.get('reponame')
    constructed = False
    if not reponame:
        reponame = os.path.split(repo.root)[1]
        constructed = True
    if '/' not in reponame:
        reponame = '%s/%s' % (getusername(ui), reponame)
        constructed = True
    if constructed:
        ui.status('using %r as repo name\n' % reponame)
    ui.status('getting descendants list\n')
    fp = urllib.urlopen('http://bitbucket.org/%s/descendants' % reponame)
    if fp.getcode() != 200:
        raise util.Abort('getting bitbucket page failed with HTTP %s'
                         % fp.getcode())
    try:
        tree = parse(fp)
    finally:
        fp.close()
    try:
        forklist = tree.findall('//div[@class="repos-all"]')[1]
        urls = [a.attrib['href'] for a in forklist.findall('div/a')]
        if len(urls) == 1 and urls[0].endswith(reponame + '/overview'):
            ui.status('this repository has no forks yet\n')
            return
    except Exception:
        raise util.Abort('scraping bitbucket page failed')
    forks = [(urlparse.urlsplit(url)[2][1:], url) for url in urls]
    # filter out ignored forks
    ignore = set(ui.configlist('bb', 'ignore_forks'))
    forks = [(name, url) for (name, url) in forks if name not in ignore]

    if opts.get('incoming'):
        templateopts = {}
        if not opts.get('full'):
            templateopts['template'] = '\xff'
        for name, url in forks:
            ui.status('looking at bb+http:%s\n' % name)
            try:
                if not opts.get('full'): ui.quiet = True
                ui.pushbuffer()
                try:
                    commands.incoming(ui, repo, url, bundle='', **templateopts)
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
          ('i', 'incoming', None, 'look for incoming changesets'),
          ('f', 'full', None, 'show full incoming info'),
          ],
         'hg bbforks [-n reponame]')
}
