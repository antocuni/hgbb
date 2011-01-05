# -*- coding: utf-8 -*-
#
# bitbucket.org mercurial extension
#
# Copyright (c) 2009, 2010, 2011 by Armin Ronacher, Georg Brandl.
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

The ``lxml`` module is required for operations that need to scrape pages
from bitbucket.org (currently bbforks).

Configuration::

    [bb]
    username = your bitbucket username
    password = your bitbucket http password for http (otherwise you'll be asked)
    default_method = the default checkout method to use (ssh or http)

There is one additional configuration value that makes sense only in
repository-specific configuration files::

    ignore_forks = comma-separated list of forks you'd like to ignore in bbforks

The forks are given by bitbucket repository names (``username/repo``).

Implemented URL schemas, usable instead of ``https://bitbucket.org/...``:

bb://repo
    clones your own "repo" repository, checkout via default method
bb://username/repo
    clones the "repo" repository by username, checkout via default method
bb+http://repo
    clones your own "repo" repository, checkout via http
bb+http://username/repo
    clones the "repo" repository by username, checkout via http
bb+ssh://repo
    clones your own "repo" repository, checkout via ssh
bb+ssh://username/repo
    clones the "repo" repository by username, checkout via ssh

Note: you can omit the two slashes (e.g. ``bb:user/repo``) when using the
URL on the command line.  It will *not* work when put into the [paths]
entry in hgrc.
"""

from mercurial import hg, commands, sshrepo, httprepo, util, error, extensions

import os
import urllib
import urlparse

# utility functions

def get_username(ui):
    """Return the bitbucket username or guess from the login name."""
    username = ui.config('bb', 'username', None)
    if username:
        return username
    import getpass
    username = getpass.getuser()
    ui.status('using system user %r as username' % username)
    return username

def parse_repopath(path):
    if '://' in path:
        parts = urlparse.urlsplit(path)
        # http or ssh full path
        if parts[1].endswith('bitbucket.org'):
            return parts[2].strip('/')
        # bitbucket path in schemes style (bb://name/repo)
        elif parts[0].startswith('bb'):
            # parts[2] already starts with /
            return ''.join(parts[1:3]).strip('/')
    # bitbucket path in hgbb style (bb:name/repo)
    elif path.startswith('bb:'):
        return path[3:]
    elif path.startswith('bb+') and ':' in path:
        return path.split(':')[1]


def get_bbreponame(ui, repo, opts):
    reponame = opts.get('reponame')
    constructed = False
    if not reponame:
        # try to guess from the "default" or "default-push" repository
        paths = ui.configitems('paths')
        for name, path in paths:
            if name == 'default' or name == 'default-push':
                reponame = parse_repopath(path)
                if reponame:
                    break
        else:
            # guess from repository pathname
            reponame = os.path.split(repo.root)[1]
        constructed = True
    if '/' not in reponame:
        reponame = '%s/%s' % (get_username(ui), reponame)
        constructed = True
    # if we guessed or constructed the name, print it out for the user to avoid
    # unwanted surprises
    if constructed:
        ui.status('using %r as repo name\n' % reponame)
    return reponame


# bb: schemes repository classes

class bbrepo(object):
    """Short URL to clone from or push to bitbucket."""

    def __init__(self, factory, url):
        self.factory = factory
        self.url = url

    def instance(self, ui, url, create):
        scheme, path = url.split(':', 1)
        if path.startswith('//'):
            path = path[2:]
        username = get_username(ui)
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
        if method == 'http':
            method = 'https'
        return hg.schemes['bb+' + method].instance(ui, url, create)


def list_forks(reponame):
    try:
        from lxml.html import parse
    except ImportError:
        raise util.Abort('lxml.html is (currently) needed to run bbforks')

    try:
        tree = parse(urllib.urlopen('https://bitbucket.org/%s/descendants/' % reponame))
    except IOError, e:
        raise util.Abort('getting bitbucket page failed with:\n%s' % e)

    try:
        forklist = tree.findall('//div[@class="forks pane"]')[0]
        urls = [a.attrib['href'][:-9] for a in forklist.findall('ol/li/span/a')
                if a.attrib['href'].endswith('/overview')]
        if not urls:
            return []
    except Exception, e:
        raise util.Abort('scraping bitbucket page failed:\n' + str(e))

    forks = [urlparse.urlsplit(url)[2][1:] for url in urls]
    return forks


# new commands

FULL_TMPL = '''\xff{rev}:{node|short} {date|shortdate} {author|user}: \
{desc|firstline|strip}\n'''

def bb_forks(ui, repo, **opts):
    '''list all forks of this repo at bitbucket

    An explicit bitbucket reponame (``username/repo``) can be given with the
    ``-n`` option.

    With the ``-i`` option, check each fork for incoming changesets.  With the
    ``-i -f`` options, also show the individual incoming changesets like
    :hg:`incoming` does.
    '''

    reponame = get_bbreponame(ui, repo, opts)
    ui.status('getting descendants list\n')
    forks = list_forks(reponame)
    if not forks:
        ui.status('this repository has no forks yet\n')
        return
    # filter out ignored forks
    ignore = set(ui.configlist('bb', 'ignore_forks'))
    forks = [name for name in forks if name not in ignore]

    if opts.get('incoming'):
        templateopts = {'template': opts.get('full') and FULL_TMPL or '\xff'}
        for name in forks:
            ui.status('looking at %s\n' % name)
            try:
                ui.quiet = True
                ui.pushbuffer()
                try:
                    commands.incoming(ui, repo, 'bb://' + name, bundle='',
                                      force=False, newest_first=True,
                                      **templateopts)
                finally:
                    ui.quiet = False
                    contents = ui.popbuffer(True)
            except (error.RepoError, util.Abort), msg:
                ui.warn('Error: %s\n' % msg)
            else:
                if not contents:
                    continue
                number = contents.count('\xff')
                if number:
                    ui.status('%d incoming changeset%s found in bb://%s\n' %
                              (number, number > 1 and 's' or '', name),
                              label='status.modified')
                ui.write(contents.replace('\xff', ''), label='log.changeset')
    else:
        for name in forks:
            ui.status('bb://%s\n' % name)
            #json = urllib.urlopen(
            #    'http://api.bitbucket.org/1.0/repositories/%s/' % name).read()


def clone(orig, ui, source, dest=None, **opts):

    if source[:2] == 'bb' and ':' in source:
        protocol, rest = source.split(':', 1)
        if rest[:2] != '//':
            source = '%s://%s' % (protocol, rest)

    return orig(ui, source, dest, **opts)

def uisetup(ui):
    extensions.wrapcommand(commands.table, 'clone', clone)


hg.schemes['bb'] = auto_bbrepo()
hg.schemes['bb+http'] = bbrepo(
    httprepo.instance, 'https://%(auth)sbitbucket.org/%(path)s')
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
         'hg bbforks [-i [-f]] [-n reponame]')
}
