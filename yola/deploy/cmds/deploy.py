#!/usr/bin/env python

import argparse
import logging
import os
import socket
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import yola.deploy.application
import yola.deploy.config
import yola.deploy.repository

# Replaced when configured
log = logging.getLogger(__name__)


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
                        default='master')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Increase verbosity')
    parser.add_argument('-c', '--config', metavar='FILE',
                        default=yola.deploy.config.find_deploy_config(False),
                        help='Location of the Deploy configuration file.')

    opts = parser.parse_args()

    if opts.command in shortcuts:
        opts.command = shortcuts[opts.command]

    if opts.config is None:
        # Yes, it was a default, but we want to prent the error
        opts.config = yola.deploy.config.find_deploy_config()

    return opts


def configure_logging(verbose, deploy_settings):
    "Set up logging, return the logger for this script"
    global log

    logging.basicConfig(level=logging.DEBUG)
    root = logging.getLogger()

    for handler in root.handlers:
        handler.setLevel(level=logging.DEBUG if verbose else logging.INFO)

    conf = deploy_settings.logging

    handler = logging.FileHandler(conf.logfile)
    handler.setLevel(logging.INFO)
    root.addHandler(handler)

    if 'debug_logfile' in conf:
        handler = logging.handlers.RotatingFileHandler(
                conf.debug_logfile, backupCount=conf.debug_history)
        handler.doRollover()
        handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(handler)

    logging.getLogger('boto').setLevel(logging.WARNING)

    log = logging.getLogger(os.path.basename(__file__).rsplit('.', 1)[0])


def report(app, action, message, deploy_settings):
    "Report to the world that we deployed."

    user = os.getenv('SUDO_USER', os.getenv('LOGNAME'))
    environment = deploy_settings.environment
    hostname = socket.gethostname()
    fqdn = socket.getfqdn()

    message = '%s@%s: %s' % (user, fqdn, message)

    log.info(message)

    if 'statsd' in deploy_settings:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = (deploy_settings.statsd.host, deploy_settings.statsd.port)
        sock.sendto('deploys.%s.%s.%s:1|c' % (environment, hostname, app),
                    addr)

    if 'campfire' in deploy_settings:
        try:
            from pinder.campfire import Campfire

            log.info('Creating campfire report')
            room = deploy_settings.campfire.get('room', 'Platform')
            connection = Campfire(deploy_settings.campfire.subdomain,
                                  deploy_settings.campfire.token,
                                  ssl=True)
            emoji = ' :collision:' if environment == 'production' else ''
            connection.find_room_by_name(room).speak(message + emoji)
        except ImportError:
            log.error('Unable to import pinder for campfire reporting')


def available_applications(deploy_settings):
    "Return the applications available for deployment"

    available_applications = deploy_settings.available_applications
    if available_applications is True:
        repository = yola.deploy.repository.get_repository(deploy_settings)
        return repository.list_apps()
    return available_applications


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

    if opts.app not in available_applications(deploy_settings):
        log.error('This application is not in the available applications '
                  'list. Please check your deploy config.')
        sys.exit(1)

    repository = yola.deploy.repository.get_repository(deploy_settings)
    application = yola.deploy.application.Application(
            opts.app, opts.target, repository, opts.config)

    version = opts.version
    if version is None:
        version = repository.latest_version(opts.app, opts.target)

    application.deploy(version)
    message = 'Deployed %s/%s' % (application.app, version)
    report(application.app, 'deploy', message, deploy_settings)


def main():
    "Dispatch"
    opts = parse_args()
    deploy_settings = yola.deploy.config.load_settings(opts.config)
    configure_logging(opts.debug, deploy_settings)
    log.debug('Running: %r', sys.argv)
    if opts.target is None:
        opts.target = deploy_settings.get('target')

    cmd = globals().get('do_%s' % opts.command.replace('-', '_'))
    if cmd:
        cmd(opts, deploy_settings)
    else:
        log.error('Unsupported command: %s', opts.command)
        sys.exit(1)


if __name__ == '__main__':
    main()