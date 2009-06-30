# -*- coding: utf-8 -*-
"""
    hgbb
    ~~~~

    This extension provides simple access to some bitbucket features such as
    repository creation and checkout via short URL schemes.

    Configuration Values::

        [bb]
        username = your bitbucket username
        password = your bitbucket http password if you're using http checkout
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

    :copyright: 2009 by Armin Ronacher.
    :license:
        This program is free software; you can redistribute it and/or modify it
        under the terms of the GNU General Public License as published by the
        Free Software Foundation; either version 2 of the License, or (at your
        option) any later version.

        This program is distributed in the hope that it will be useful, but
        WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
        Public License for more details.

        You should have received a copy of the GNU General Public License along
        with this program; if not, write to the Free Software Foundation, Inc.,
        51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""
import sys

from mercurial import commands, cmdutil, patch, sshrepo, httprepo, hg, ui, util


def getusername(ui):
    """Return the bitbucket username or guess from the login name."""
    username = ui.config('bb', 'username', None)
    if username:
        return username
    import getpass
    return getpass.getuser()


def bb_create(ui, repo, reponame, **opts):
    print reponame, opts


class BBRepo(object):
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


class AutoRepo(object):

    def instance(self, ui, url, create):
        method = ui.config('bb', 'default_method', 'https')
        if method not in ('ssh', 'http', 'https'):
            raise util.Abort('Invalid config value for paste.default_method: %s' % method)
        return hg.schemes['bb+' + method].instance(ui, url, create)


## Waiting for the API :)
#cmdtable = {
#    'bbcreate':
#        (bb_create,
#         [('p', 'private', None, 'create a private repository'),
#          ('w', 'website', '', 'the website for the repository'),
#          ('d', 'description', '', 'the description for the repository')],
#         'hg bbcreate REPOSITORY [-p]')
#}

hg.schemes['bb'] = AutoRepo()
hg.schemes['bb+http'] = BBRepo(httprepo.instance, 'http://%(auth)sbitbucket.org/%(path)s')
hg.schemes['bb+https'] = BBRepo(httprepo.instance, 'https://%(auth)sbitbucket.org/%(path)s')
hg.schemes['bb+ssh'] = BBRepo(sshrepo.sshrepository, 'ssh://hg@bitbucket.org/%(path)s')
