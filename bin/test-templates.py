#!/usr/bin/env python
import argparse
import itertools
import logging
import os
import sys

import tempita
from yoconfigurator.smush import (config_sources, local_config_sources,
                                  smush_config)


log = logging.getLogger('test_templates')


def build_config(app, env, cluster, local, deployconfigs):
    app_config = 'deploy/configuration'
    deployconfigs = [deployconfigs]
    if local:
        deployconfigs.append(os.path.join(app_config, 'local'))
    sources = config_sources(app, env, cluster, deployconfigs, app_config)
    if local:
        sources = itertools.chain(sources,
                local_config_sources(app, deployconfigs, app_config))

    return smush_config(sources)


def template(filename, app, config):
    tmpl = tempita.Template.from_filename(filename)

    tmpl.substitute(conf=config,
                    aconf=config.get(app, {}),
                    cconf=config.get('common', {}))


def test_templates(app, env, cluster, local, configs_dir):
    config = build_config(app, env, cluster, local, configs_dir)
    for root, dirs, files in os.walk('deploy/templates'):
        for fn in files:
            if fn.startswith('.'):
                continue
            log.debug('Parsing template: %s in %s/%s', fn, env, cluster)
            template(os.path.join(root, fn), app, config)


def main():
    p = argparse.ArgumentParser(prog='test_templates',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('-d', '--configs-dir', metavar='DIR',
                   help='Location of the deployconfigs')
    p.add_argument('-e', '--environments', metavar='ENV,ENV',
                   default='production,qa,integration',
                   help='Comma-separated list of environment[:cluster] to test')
    p.add_argument('--app-dir', '-a', metavar='DIRECTORY',
                   default='.',
                   help='Location of the application.')
    p.add_argument('--verbose', '-v',
                   action='store_true',
                   help="Make a noise")
    p.add_argument('app', help='Application name')

    options = p.parse_args()

    if options.verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    os.chdir(options.app_dir)
    for env in options.environments.split(','):
        cluster = None
        if ':' in env:
            cluster, env = env.split(':', 1)
        for local in False, True:
            test_templates(options.app, env, cluster, local,
                           options.configs_dir)


if __name__ == '__main__':
    main()
