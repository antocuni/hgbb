Bitbucket support for Mercurial
===============================

Features
--------

* short URLs for bitbucket projects: bb:user/repo
* looking for incoming changes in all forks bitbucket knows about
* listing all followers of the repo
* getting link to the repository or the any file
* creating repo on bitbucket

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


