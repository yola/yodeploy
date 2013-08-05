#!/usr/bin/env python

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from yodeploy.deploy import (available_applications, configure_logging, deploy,
                             load_defaults)
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

    return opts


def do_available_apps(opts):
    "List available applications"

    apps = available_applications(opts.deploy_settings)
    if apps:
        print 'Available Applications:'
        for app in apps:
            print ' * %s' % app
    else:
        print 'No available applications'


def do_deploy(opts):
    "Deploy an application"
    deploy(opts.app, opts.target, opts.config, opts.version,
           opts.deploy_settings)


def main():
    "Dispatch"
    opts = parse_args()
    opts = load_defaults(opts)
    log = configure_logging(opts.debug, opts.deploy_settings.logging)
    log.debug('Running: %r', sys.argv)

    cmd = globals().get('do_%s' % opts.command.replace('-', '_'))
    if cmd:
        cmd(opts)
    else:
        log.error('Unsupported command: %s', opts.command)
        sys.exit(1)


if __name__ == '__main__':
    main()
