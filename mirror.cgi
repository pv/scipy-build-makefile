#!/usr/bin/env python
"""
%prog

CGI script for updating remote Git-SVN mirrors that require SSH keys to push.

1. Clone and prepare Git-SVN mirrors to a working directory.
   Ensure that 'git svn rebase' works.

2. Push them initially to wherever you host them.
   Ensure that the 'git svn push .....' command works as intended.

3. Edit the REPOS and SSH_KEY config items in this script accordingly.

4. Set up this script as a CGI script somewhere.

5. Add a 'post-commit' hook to SVN that pokes the CGI script.

"""
#------------------------------------------------------------------------------
# Settings
#------------------------------------------------------------------------------

REPOS = {
    'numpy': ('/home/pauli/koodi/proj/scipy/numpy-svn.git',
              'git@github.com:pv/numpy-svn.git'),
    'scipy': ('/home/pauli/koodi/proj/scipy/scipy-svn.git',
              'git@github.com:pv/scipy-svn.git'),
}

SSH_KEY = "/home/pauli/.ssh/push_id_rsa"

ALLOWED_IP = ['0.0.0.0/0']

#------------------------------------------------------------------------------
import cgi
import os
import sys
import struct
from optparse import OptionParser
from subprocess import call, Popen, PIPE

def main():
    p = OptionParser(__doc__.strip())
    p.add_option("--process", action="store_true")
    options, args = p.parse_args()

    env = os.environ
    
    if options.process:
        for name in args:
            repo = REPOS.get(name)
            if repo:
                update_mirror(repo)
    elif not match_ip(env.get('REMOTE_ADDR'), ALLOWED_IP):
        print "Content-type: text/plain\n\nDENY"
    else:
        path = env.get('PATH_INFO', '')
        repo_name = path.strip('/').strip()
        if repo_name not in REPOS:
            print "Content-type: text/plain\n\nNOP"
            return

        spawn_repo_update(repo_name)
        print "Content-type: text/plain\n\nOK"

def update_mirror(repo):
    """
    Update given Git-SVN mirror

    """
    basedir, remote = repo

    os.chdir(basedir)

    p = Popen(['git', 'svn', 'rebase'], stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    if 'is up to date' in out+err:
        # nothing to do
        call(['touch', '/tmp/fubar'])
        return

    call(['ssh-add', SSH_KEY])
    call(['git', 'push', remote, '--all'])
    call(['git', 'push', remote, '+refs/remotes/*:refs/remotes/*'])

def spawn_repo_update(repo_name):
    """
    Run a repository update, spawning ssh-agent as necessary.
    """
    if daemonize() == 'child':
        os.environ.pop('DISPLAY', None)
        if 'SSH_AUTH_SOCK' in os.environ:
            call([sys.argv[0], '--process', repo_name])
        else:
            call(['ssh-agent', sys.argv[0], '--process', repo_name])

def daemonize():
    """
    Fork and daemonize a child process in the background.
    Returns 'child' and 'parent', for the child and the parent processes.

    """
    # 1st fork
    if os.fork() > 0:
        # leave parent
        return 'parent'

    os.setsid()

    # 2nd fork
    if os.fork() > 0:
        # close parent
        os._exit(0)

    # IO streams
    si = open('/dev/null', 'r')
    so = open('/dev/null', 'r')
    se = open('/dev/null', 'r')
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())
    sys.stdout, sys.stderr = so, se
    return 'child'

def match_ip(address, mask):
    """Check if an ip address matches the specified net mask"""

    if address is None:
        address = '0.0.0.0'

    if isinstance(mask, list):
        for m in mask:
            if match_ip(address, m):
                return True
        return False

    if isinstance(address, str):
        addr_ip = inet_atoi(address)
    else:
        addr_ip = address

    if isinstance(mask, str):
        mask = mask.strip()
        if '/' in mask:
            mask, nbits = mask.split('/', 1)
            mask_ip = inet_atoi(mask)
            nbits = 32 - int(nbits)
        else:
            mask_ip = inet_atoi(mask)
            nbits = 0
    else:
        mask_ip = mask
        nbits = 0

    return (addr_ip >> nbits) == (mask_ip >> nbits)

def inet_atoi(s):
    """Convert dotted-quad IP address to long"""
    a, b, c, d = map(int, s.split('.'))
    return ((a&0xFF) << 24) | ((b&0xFF) << 16) | ((c&0xFF) << 8) | (d&0xFF)

if __name__ == "__main__":
    main()
