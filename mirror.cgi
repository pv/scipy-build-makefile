#!/usr/bin/env python
"""
%prog [OPTIONS] MODE ARGUMENTS...

Update remote Git-SVN mirrors that can require SSH keys to push.

Modes:

  cgi CONFFILE
      Function as a CGI script. URL '%prog/REPO/SECRETKEY'
      triggers a background upgrade of a given repository, provided
      the secret key matches that given in the config file.

      Consider also limiting access to the URL, to prevent denial of service
      attacks.

  daemon CONFFILE
      Function as a daemon that listens on a TCP port.
      Writing 'REPO SECRETKEY' (eg. with the 'telnet' command)
      to the port causes it to trigger an update.

  update CONFFILE REPO
      Update the given repository.

Configuration file:

  [global]
  secret_key = A secret key for the CGI/daemon modes.
  log_file = Path to the log file (used for CGI/daemon mode). Optional.
  pid_file = Path to the pid file (user for daemon mode). Optional.
  port = TCP port to listen on (used for daemon mode). Default: 3898

  [REPO1]
  vcs = git
  local = Local path.
  remote = Remote URL where to upload.
  git_svn_init = Arguments to 'git-svn init' for initial clone.
  git_svn_fetch = Arguments to 'git-svn fetch' for initial clone.
  ssh_key = The SSH private key needed for uploading. Optional.

  [REPO2]
  ...

"""
#------------------------------------------------------------------------------
import cgi
import os
import re
import sys
import struct
import shutil
import time
import socket
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
        run_cgi(validate_config(Config.load(config_file)))
    elif mode == 'daemon':
        if args:
            p.error("extraneous arguments given")
        run_daemon(validate_config(Config.load(config_file)))
    elif mode == 'update':
        if not args:
            p.error("no repository to update given")
        config = validate_config(Config.load(config_file))
        for name in args:
            if not config.is_repo(name):
                p.error("unknown repository '%s'" % name)
        run_update(args, config)
    else:
        p.error("unknown mode '%s'" % mode)

def run_update(repos, config):
    for name in repos:
        c = config[name]
        VCSS[c.vcs][0](c)

#------------------------------------------------------------------------------
# CGI mode
#------------------------------------------------------------------------------

def run_cgi(config):
    env = os.environ

    path = env.get('PATH_INFO', '').strip().strip('/').strip()

    if '/' in path:
        repo_name, secret_key = path.split('/', 1)
    else:
        repo_name = None

    if not config.is_repo(repo_name):
        print "Content-type: text/plain\n\nNOP"
        return

    if secret_key != config['global'].secret_key:
        print "Content-type: text/plain\n\nNOP"
        return

    spawn_repo_update(config, repo_name)

    print "Content-type: text/plain\n\nOK"

#------------------------------------------------------------------------------
# Daemon mode
#------------------------------------------------------------------------------

def run_daemon(config):
    cfg = config['global']

    listen_addr = ('', cfg.port)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(listen_addr)
    s.listen(1)

    if daemonize(cfg.log_file) == 'parent':
        print "Daemon spawned"
        return

    if cfg.pid_file:
        f = open(cfg.pid_file, 'w')
        f.write("%d" % os.getpid)
        f.close()

    print "!! Pid %d listening on %s:%s" % (os.getpid(), listen_addr[0],
                                            listen_addr[1])

    while True:
        conn, addr = s.accept()
        print "!! Connect from ", addr
        data = conn.recv(1024)
        conn.close()

        r = data.strip().split()
        if len(r) != 2:
            print "!! Bad input from", addr
            continue
        
        repo_name, secret = r
        if secret != cfg.secret_key:
            print "!! Bad secret from", addr
            continue
        if not config.is_repo(repo_name):
            print "!! Bad repo from", addr
            continue

        spawn_repo_update(config, repo_name)


#------------------------------------------------------------------------------
# General
#------------------------------------------------------------------------------

def validate_config(config):
    for name in config.keys():
        try:
            section = config[name]
            new_section = Config()

            if name == 'global':
                # Global section
                new_section.secret_key = section.secret_key
                new_section.log_file = section.get('log_file', None)
                new_section.pid_file = section.get('pid_file', None)
                new_section.port = int(section.get('port', 3898))
            else:
                # Repository sections
                if 'vcs' not in section:
                    raise ConfigError("Key 'vcs' not given")
                if section.vcs == 'git':
                    new_section = git_validate_config(section)
                    new_section.vcs = 'git'
                else:
                    raise ConfigError("Vcs '%s' is unknown" % section.vcs)

            # Check that the config file contains only known keys
            for key in section.keys():
                if key not in new_section:
                    raise ConfigError("Spurious key '%s'" % key)

            # Done.
            config[name] = new_section
        except ValueError, err:
            raise ConfigError(err.args[0] + " in section '%s'" % name)
        except ConfigError, err:
            raise ConfigError(err.args[0] + " in section '%s'" % name)
    return config

def spawn_repo_update(config, repo_name):
    """
    Run a repository update, spawning ssh-agent as necessary.
    """
    if daemonize(config['global'].log_file) == 'child':
        print "!! Spawning (pid %d)" % os.getpid()
        try:
            os.environ.pop('DISPLAY', None)
            cmd = ['ssh-agent', sys.argv[0], 'update', config._filename,
                   repo_name]
            exec_command(cmd, quiet=False)
        finally:
            print "!! Done (pid %d)" % os.getpid()
        sys.exit(0)


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
    new.git_svn_init = config.get('git_svn_init', '').split()
    new.git_svn_fetch = config.get('git_svn_fetch', '').split()
    return new

def git_update_mirror(repo):
    """
    Update given Git-SVN mirror

    """
    # Lock
    if not os.path.isdir(repo.local):
        os.makedirs(repo.local)
    lock = LockFile(os.path.join(repo.local, '.update-lock'))
    lock.acquire()
    try:
        _git_update_mirror(repo)
    finally:
        lock.release()

def _git_update_mirror(repo):
    local = repo.local
    remote = repo.remote

    # Inject ssh key
    if repo.ssh_key:
        exec_command(['ssh-add', repo.ssh_key])

    print "++ Updating repository %s ..." % local

    if not os.path.isdir(os.path.join(local, '.git')):
        # Local repository missing
        if not os.path.isdir(local):
            os.makedirs(local)

        try:
            print "-- Repository missing; trying to clone from remote..."
            os.chdir(local)
            exec_command(['git', 'init'])
            exec_command(['git', 'fetch', remote,
                          '+refs/remotes/*:refs/remotes/*'])
            exec_command(['git', 'svn', 'init'] + repo.git_svn_init)
            exec_command(['git', 'co', '-b', 'master', 'trunk'])
            exec_command(['git', 'svn', 'rebase', '-l'])
        except ExecError:
            print "-- Remote clone failed; going to get everything via SVN..."
            if os.path.isdir(local):
                shutil.rmtree(path)
            os.makedirs(local)
            os.chdir(local)
            exec_command(['git', 'init'])
            exec_command(['git', 'svn', 'init'] + repo.git_svn_init)
            exec_command(['git', 'svn', 'fetch'] + repo.git_svn_fetch)

    print "-- Rebasing..."
    os.chdir(local)

    output = exec_command(['git', 'svn', 'rebase'])
    if 'is up to date' in output or 'up-to-date' in output:
        # nothing to do
        print "-- Done, already up-to-date"
        return

    print "-- Pushing..."
    exec_command(['git', 'push', remote, '--all'])
    exec_command(['git', 'push', remote, '+refs/remotes/*:refs/remotes/*'])

    print "-- Done"


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
        self._filename = filename
        self._global = Config()
        self._parse(filename)
        return self

    def is_repo(self, name):
        return (name != 'global' and name in self)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if name.startswith('_'):
            self.__dict__[name] = value
        else:
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

def daemonize(log_file=None):
    """
    Fork and daemonize a child process in the background.
    Returns 'child' and 'parent', for the child and the parent processes.

    """
    # Try to open log file; just to check if it works
    if log_file:
        f = open(log_file, 'a')
        f.close()

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
    if log_file is None:
        so = open('/dev/null', 'r')
        se = open('/dev/null', 'r')
    else:
        so = open(log_file, 'a', 0) # unbuffered
        se = so

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

class LockFile(object):
    # XXX: posix-only

    def __init__(self, filename):
        self.filename = filename
        self.pid = os.getpid()
        self.count = 0

    def __enter__(self):
        self.acquire()

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()

    def acquire(self, block=True):
        if self.count > 0:
            self.count += 1
            return True
        
        while True:
            try:
                lock_pid = os.readlink(self.filename)
                if not os.path.isdir('/proc/%s' % lock_pid):
                    # dead lock; delete under lock to avoid races
                    sublock = LockFile(self.filename + '.lock')
                    sublock.acquire()
                    try:
                        os.unlink(self.filename)
                    finally:
                        sublock.release()
            except OSError, exc:
                pass

            try:
                os.symlink(repr(self.pid), self.filename)
                break
            except OSError, exc:
                if exc.errno != 17: raise

            if not block:
                return False
            time.sleep(1)

        self.count += 1
        return True

    def release(self):
        if self.count == 1:
            os.unlink(self.filename)
        elif self.count < 1:
            raise RuntimeError('Invalid lock nesting')
        self.count -= 1


#------------------------------------------------------------------------------

if __name__ == "__main__":
    main()
