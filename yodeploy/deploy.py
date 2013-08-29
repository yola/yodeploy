import json
import logging
import os
import socket
import sys

import requests
from requests.exceptions import RequestException

import yodeploy.application
import yodeploy.config
import yodeploy.repository


def load_defaults(opts):
    "Populate opts with sensible defaults if the settings are missing"
    if not hasattr(opts, 'config'):
        opts.config = yodeploy.config.find_deploy_config()

    if not hasattr(opts, 'deploy_settings'):
        opts.deploy_settings = yodeploy.config.load_settings(opts.config)

    if not hasattr(opts, 'target'):
        opts.target = opts.deploy_settings.artifacts.target

    return opts


def configure_logging(verbose, conf, filename=None):
    "Set up logging, return the logger for this script"
    logging.basicConfig(level=logging.DEBUG, filename=filename)
    root = logging.getLogger()

    for handler in root.handlers:
        handler.setLevel(level=logging.DEBUG if verbose else logging.INFO)

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


def report(app, action, old_version, version, deploy_settings):
    "Report to the world that we deployed."

    user = os.getenv('SUDO_USER', os.getenv('LOGNAME'))
    environment = deploy_settings.artifacts.environment
    hostname = socket.gethostname()
    fqdn = socket.getfqdn()

    message = '%s@%s: Deployed %s: %s -> %s' % (user, fqdn, app, old_version,
                                                version)

    log.info(message)
    services = deploy_settings.report.services

    if 'statsd' in services:
        service_settings = deploy_settings.report.service_settings.statsd
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = (service_settings.host, service_settings.port)
        sock.sendto('deploys.%s.%s.%s:1|c'
                    % (environment, hostname, app.replace('.', '_')), addr)

    if 'campfire' in services:
        try:
            log.info('Creating campfire report')
            service_settings = deploy_settings.report.service_settings.campfire
            rooms = requests.get('https://%s.campfirenow.com/rooms.json' %
                                 service_settings.subdomain,
                                 auth=(service_settings.token, '')).json()
            room = [r for r in rooms['rooms'] if r['name'] ==
                    service_settings.room][0]

            emoji = ' :collision:' if environment == 'production' else ''
            requests.post('https://%s.campfirenow.com/room/%s/speak.json' %
                          (service_settings.subdomain, room['id']),
                          auth=(service_settings.token, ''),
                          headers={'Content-type': 'application/json'},
                          data=json.dumps({'message': {'body': message + emoji,
                                                       'type': 'TextMessage'}}))
        except IndexError:
            log.error('Unknown campfire room', service_settings.room)
        except ValueError:
            log.error('Error posting report to campfire')

    if 'webhook' in services:
        log.info('Sending deploy information to webhook')
        service_settings = deploy_settings.report.service_settings.webhook
        payload = {
            'app': app,
            'action': action,
            'old_version': old_version,
            'version': version,
            'user': user,
            'fqdn': fqdn,
            'environment': environment,
        }
        auth = None
        if service_settings.username:
            auth = (service_settings.username, service_settings.password)
        try:
            requests.post(service_settings.url,
                          auth=auth,
                          headers={'Content-type': 'application/json'},
                          data=json.dumps(payload))
        except RequestException as e:
            log.warning('Could not send post-deploy webhook: %s', e)


def available_applications(deploy_settings):
    "Return the applications available for deployment"

    if deploy_settings.apps.limit:
        return deploy_settings.apps.available

    repository = yodeploy.repository.get_repository(deploy_settings)
    return repository.list_apps()


def deploy(app, target, config, version, deploy_settings):
    "Deploy an application"
    if app not in available_applications(deploy_settings):
        log.error('This application is not in the available applications '
                  'list. Please check your deploy config.')
        sys.exit(1)

    repository = yodeploy.repository.get_repository(deploy_settings)
    application = yodeploy.application.Application(app, target, repository,
                                                   config)

    old_version = application.live_version
    if version is None:
        version = repository.latest_version(app, target)

    application.deploy(version)
    report(application.app, 'deploy', old_version, version, deploy_settings)
