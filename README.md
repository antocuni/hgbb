Bitbucket support for Mercurial
===============================

Features
--------

* short URLs for bitbucket projects: bb:user/repo
* looking for incoming changes in all forks bitbucket knows about
* listing all followers of the repo
* getting link to the repository or the any file
* creating repo on bitbucket

Mercurial configuration
-----------------------

You might write something like this to your ~/.hgrc or another hgrc file.

    [bb]
    username = your bitbucket username
    password = your bitbucket http password for http (otherwise you'll be asked)
    default_method = the default checkout method to use (ssh or http)

You can read more about hgrc [in mercurial documentation](http://www.selenic.com/mercurial/hgrc.5.html "Configuration files for Mercurial")

Short urls
----------

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
