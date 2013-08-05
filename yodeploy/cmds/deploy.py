#!/usr/bin/env python

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from yodeploy.deploy import available_applications, configure_logging, deploy
import yodeploy.config


def parse_args():
    parser = argparse.ArgumentParser(description="Deploy applications")

    subparsers = parser.add_subparsers(dest='command', title='commands',
                                       help='additional help')

    deploy_p = subparsers.add_parser('deploy',
                                     help='Deploy an application and configs')
    deploy_p.add_argument('app', help='The application name')

    subparsers.add_parser('available-apps', help='Show available applications')

    # hack in some short aliases:
    shortcuts = {}
    for k, v in subparsers._name_parser_map.items():
        subparsers._name_parser_map[k[0]] = v
        shortcuts[k[0]] = k

    parser.add_argument('--version', '-v',
                        help='Use a specific application version')
    parser.add_argument('--target', help='The target to deploy from',
                        default=None)
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Increase verbosity')
    parser.add_argument('-c', '--config', metavar='FILE',
                        default=yodeploy.config.find_deploy_config(False),
                        help='Location of the Deploy configuration file.')

    opts = parser.parse_args()

    if opts.command in shortcuts:
        opts.command = shortcuts[opts.command]

    if opts.config is None:
        # Yes, it was a default, but we want to prent the error
        opts.config = yodeploy.config.find_deploy_config()

    return opts


def do_available_apps(opts, deploy_settings):
    "List available applications"

    apps = available_applications(deploy_settings)
    if apps:
        print 'Available Applications:'
        for app in apps:
            print ' * %s' % app
    else:
        print 'No available applications'


def do_deploy(opts, deploy_settings):
    "Deploy an application"
    deploy(opts.app, opts.target, opts.config, opts.version, deploy_settings)


def main():
    "Dispatch"
    opts = parse_args()
    deploy_settings = yodeploy.config.load_settings(opts.config)
    log = configure_logging(opts.debug, deploy_settings)
    log.debug('Running: %r', sys.argv)
    if opts.target is None:
        opts.target = deploy_settings.artifacts.target

    cmd = globals().get('do_%s' % opts.command.replace('-', '_'))
    if cmd:
        cmd(opts, deploy_settings)
    else:
        log.error('Unsupported command: %s', opts.command)
        sys.exit(1)


if __name__ == '__main__':
    main()
