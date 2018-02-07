import json
import logging
import os
import socket
import sys

import requests
from requests.exceptions import RequestException

try:
    from urllib.parse import urlparse, urlunparse  # python 3
except ImportError:
    from urlparse import urlparse, urlunparse  # python 2

import yodeploy.application
import yodeploy.config
import yodeploy.repository

log = logging.getLogger(__name__)


def configure_logging(verbose, conf):
    """Set up logging."""
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
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


def strip_auth(url):
    parts = urlparse(url)
    masked = parts._replace(
        netloc=parts.hostname + (':%s' % parts.port if parts.port else ''))
    return urlunparse(masked)


def report(app, action, target, old_version, version, deploy_settings,
           user=None):
    """Report to the world that we deployed."""
    if user is None:
        user = os.getenv('SUDO_USER', os.getenv('LOGNAME'))
    environment = deploy_settings.artifacts.environment
    fqdn = socket.getfqdn()

    message = '%s@%s: Deployed %s (%s): %s -> %s' % (user, fqdn, app, target,
                                                     old_version, version)

    log.info(message)
    services = deploy_settings.report.services

    if 'webhooks' in services:
        service_settings = deploy_settings.report.service_settings.webhooks
        payload = {
            'app': app,
            'action': action,
            'target': target,
            'old_version': old_version,
            'version': version,
            'user': user,
            'fqdn': fqdn,
            'environment': environment,
        }
        for webhook_url in service_settings.urls:
            log.info('Sending deploy information to webhook: %s',
                     strip_auth(webhook_url))
            try:
                requests.post(
                    webhook_url, data=json.dumps(payload),
                    headers={'Content-type': 'application/json'})
            except RequestException as e:
                log.warning('Could not send post-deploy webhook: %s', e)


def available_applications(deploy_settings):
    """Return the applications available for deployment."""
    if deploy_settings.apps.limit:
        return deploy_settings.apps.available

    repository = yodeploy.repository.get_repository(deploy_settings)
    return repository.list_apps()


def deploy(app, target, config, version, deploy_settings, user=None):
    """Deploy an application."""
    if app not in available_applications(deploy_settings):
        log.error('This application is not in the available applications '
                  'list. Please check your deploy config.')
        sys.exit(1)

    repository = yodeploy.repository.get_repository(deploy_settings)
    application = yodeploy.application.Application(app, config)

    old_version = application.live_version
    if version is None:
        version = repository.latest_version(app, target)

    application.deploy(target, repository, version)
    report(application.app, 'deploy', target, old_version, version,
           deploy_settings, user)


def gc(max_versions, config, deploy_settings):
    """Clean up old deploys."""
    for app in available_applications(deploy_settings):
        if os.path.isdir(os.path.join(deploy_settings.paths.apps, app,
                                      'versions')):
            application = yodeploy.application.Application(app, config)
            application.gc(max_versions)
