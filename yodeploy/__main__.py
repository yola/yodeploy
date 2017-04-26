import argparse
import imp
import logging
import socket
import os

import yodeploy.repository
import yodeploy.config
import yodeploy.ipc_logging


def main():
    p = argparse.ArgumentParser(prog='yodeploy',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('-c', '--config', metavar='FILE',
                   default='/opt/deploy/config/deploy.py',
                   help='Location of the Deploy configuration file.')
    p.add_argument('-v', '--verbose', action='store_true',
                   help='Increase verbosity')
    p.add_argument('--log-fd', metavar='FD', type=int,
                   help='File descriptor referring to a Unix Domain Socket to '
                        'send pickled log events over '
                        '(not for interactive use)')
    p.add_argument('-A', '--app', metavar='NAME',
                   help='The application name '
                        '(defaults to the last part of appdir)')
    p.add_argument('appdir',
                   help='Path to the extracted application')
    p.add_argument('version',
                   help='The version of the application to operate on')
    p.add_argument('--target', metavar='TARGET',
                   default='master',
                   help='Deploy target')
    p.add_argument('-H', '--hook', metavar='HOOK',
                   help='Call HOOK in the application')
    args = p.parse_args()

    setup_logging(args.log_fd, args.verbose)

    app = os.path.basename(os.path.abspath(args.appdir))
    deploy_settings = yodeploy.config.load_settings(args.config)

    repository = yodeploy.repository.get_repository(deploy_settings)

    if args.hook:
        call_hook(app, args.target, args.appdir, args.version, deploy_settings,
                  repository, args.hook)


def setup_logging(log_fd, verbose):
    if log_fd:
        logging.basicConfig(level=0)
        logger = logging.getLogger()
        # Remove the default stdout stream handler
        for handler in logger.handlers:
            logger.removeHandler(handler)

        sock = socket.fromfd(log_fd, socket.AF_UNIX, socket.SOCK_STREAM)
        handler = yodeploy.ipc_logging.ExistingSocketHandler(sock)
        logger.addHandler(handler)
    elif verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig()


def call_hook(app, target, appdir, version, deploy_settings, repository,
              hook):
    '''Load and fire a hook'''
    fake_mod = '_deploy_hooks'
    fn = os.path.join(appdir, 'versions', version, 'deploy', 'hooks.py')
    description = ('.py', 'r', imp.PY_SOURCE)

    with open(fn, 'rb') as f:
        m = imp.load_module(fake_mod, f, fn, description)
    hooks = m.hooks(app, target, appdir, version, deploy_settings,
                    repository)
    getattr(hooks, hook)()


if __name__ == '__main__':
    main()
