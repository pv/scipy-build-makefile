#!/usr/bin/env python
"""
%prog [OPTIONS] MODE ARGUMENTS...

CGI script for updating remote Git-SVN mirrors that require SSH keys to push.

Modes:

  cgi CONFFILE
      Function as a CGI script. Accessing URL '%prog/REPO' triggers
      an background upgrade of a given repository.

      Consider limiting access to the URL, to prevent denial of service
      attacks.

  update CONFFILE REPO
      Update the given repository.

Configuration file:

  [REPO]
  local = Local path.
  remote = Remote URL where to upload.
  git-svn-init = Arguments to 'git-svn init' for initial clone.
  ssh-key = The SSH private key needed for uploading. Optional.

"""
#------------------------------------------------------------------------------
import cgi
import os
import re
import sys
import struct
from optparse import OptionParser
from subprocess import Popen, PIPE

def main():
    p = OptionParser(__doc__.strip())
    options, args = p.parse_args()

    if len(args) < 2:
        p.error("mode and configuration file not given")

    mode = args.pop(0)
    config_file = args.pop(0)

    if mode == 'cgi':
        if args:
            p.error("extraneous arguments given")
        run_cgi(options, validate_config(Config.load(config_file)))
    elif mode == 'update':
        if not args:
            p.error("no repository to update given")
        config = validate_config(Config.load(config_file))
        for name in args:
            if name not in config:
                p.error("unknown repository '%s'" % name)
        run_update(args, config)
    else:
        p.error("unknown mode '%s'" % mode)

def run_update(repos, config):
    for name in repos:
        c = config[name]
        VCSS[c.vcs][0](c)

def run_cgi(config):
    env = os.environ

    path = env.get('PATH_INFO', '')
    repo_name = path.strip('/').strip()
    if repo_name not in config:
        print "Content-type: text/plain\n\nNOP"
        return

    spawn_repo_update(repo_name)
    print "Content-type: text/plain\n\nOK"

def validate_config(config):
    for name in config.keys():
        try:
            section = config[name]
            if 'vcs' not in section:
                raise ConfigError("Key 'vcs' not given")
            if section.vcs == 'git':
                config[name] = git_validate_config(section)
                config[name].vcs = 'git'
            else:
                raise ConfigError("Vcs '%s' is unknown" % section.vcs)
        except ConfigError, err:
            raise ConfigError(err.args[0] + " in section '%s'" % name)
    return config

#------------------------------------------------------------------------------
# Updating a Git mirror
#------------------------------------------------------------------------------

def git_validate_config(config):
    new = Config()
    try:
        for key in ('local', 'remote', 'git_svn_init'):
            new[key] = config[key]
    except KeyError, err:
        raise ConfigError("No value for key '%s'" % (err.args[0],))
    new.ssh_key = config.get('ssh_key', None)
    new.init_options = config.get('git_svn_init', '').split()
    new.fetch_options = config.get('git_svn_fetch', '').split()
    return new

def git_update_mirror(repo):
    """
    Update given Git-SVN mirror

    """

    local = repo.local
    remote = repo.remote

    print "++ Updating repository %s ..." % local

    if not os.path.isdir(local):
        # Local repository missing
        basedir = os.path.dirname(local)
        if not os.path.isdir(basedir):
            os.makedirs(basedir)

        try:
            print "-- Repository missing; trying to clone from remote..."
            exec_command(['git', 'clone', remote, local])
            exec_command(['git', 'svn', 'init'] + repo.init_options)
            exec_command(['git', 'fetch', remote,
                          '+refs/remotes/*:refs/remotes/*'])
        except ExecError:
            print "-- Remote clone failed; going to get everything via SVN..."
            if os.path.isdir(local):
                shutil.rmtree(path)
            os.makedirs(local)
            os.chdir(local)
            exec_command(['git', 'init'])
            exec_command(['git', 'svn', 'init'] + repo.init_options)
            exec_command(['git', 'svn', 'fetch'] + repo.fetch_options)

    print "-- Rebasing..."
    os.chdir(local)

    output = exec_command(['git', 'svn', 'rebase'])
    if 'is up to date' in output:
        # nothing to do
        print "-- Already up-to-date."
        return

    print "-- Pushing..."
    if ssh_key:
        exec_command(['ssh-add', SSH_KEY])
    exec_command(['git', 'push', remote, '--all'])
    exec_command(['git', 'push', remote, '+refs/remotes/*:refs/remotes/*'])

    print "-- Done..."

def spawn_repo_update(repo_name):
    """
    Run a repository update, spawning ssh-agent as necessary.
    """
    if daemonize() == 'child':
        os.environ.pop('DISPLAY', None)
        if 'SSH_AUTH_SOCK' in os.environ:
            exec_command([sys.argv[0], '--process', repo_name], quiet=True)
        else:
            exec_command(['ssh-agent', sys.argv[0], '--process', repo_name],
                         quiet=True)


#------------------------------------------------------------------------------
# List of VCS
#------------------------------------------------------------------------------

VCSS = {
    'git': (git_update_mirror, git_validate_config),
}


#------------------------------------------------------------------------------
# Config parsing
#------------------------------------------------------------------------------

class ConfigError(RuntimeError):
    pass

class Config(dict):
    @classmethod
    def load(cls, filename):
        self = cls()
        self._parse(filename)
        return self

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value

    def copy(self):
        new = Config(dict(self))
        for key, value in new.items():
            if isinstance(value, Config):
                new[key] = value.copy()
        return new

    def _parse(self, filename):
        f = open(filename, 'r')
        try:
            comment_re = re.compile(r"^\s*#.*$")
            header_re = re.compile(r"^\s*\[(.*)\]\s*$")
            key_re = re.compile(r"^([a-zA-Z0-9_-]+)\s*=\s*(.*?)\s*$")
            section = 'global'
            for line in f:
                if not line.strip(): continue
                m = comment_re.match(line)
                if m:
                    continue
                m = header_re.match(line)
                if m:
                    section = m.group(1).strip()
                    continue
                m = key_re.match(line)
                if m:
                    self.setdefault(section, Config())[m.group(1)] = m.group(2)
                    continue
                raise ConfigError("Unparseable line in config: %s" % line)
        finally:
            f.close()

#------------------------------------------------------------------------------
# Utility functions
#------------------------------------------------------------------------------

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

class ExecError(RuntimeError):
    pass

def exec_command(cmd, ok_return_value=0, quiet=False):
    """
    Run given command, check return value, and return
    concatenated stdout and stderr.
    """
    try:
        if not quiet:
            print "$ %s" % " ".join(cmd)
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, stdin=PIPE)
        out, err = p.communicate()
        if not quiet:
            if out:
                print out
            if err:
                print err
    except OSError, e:
        raise RuntimeError("Command %s failed: %s" % (' '.join(cmd), e))
        
    if ok_return_value is not None and p.returncode != ok_return_value:
        raise ExecError("Command %s failed (code %d): %s"
                        % (' '.join(cmd), p.returncode, out + err))
    return out + err


#------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
