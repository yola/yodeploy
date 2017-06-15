Change Log
==========

0.8.2
-----

* `DjangoApp`: Correctly detect Django version used. Until now yodeploy
  has incorrectly assumed >= 1.7, when performing migrations.

0.8.1
-----

* Add compat 5 for pure Python 3 apps.
* Internal API changes to `yodeploy.virtualenv`:
  - Added `get_python_version`, to return the Python version that an app
    will run under.
  - `get_id`, `create_ve`, `relocateable_ve` now require a
    `python_version` argument.
  - Replaced `install_requirements` with `pip_install`.

0.8.0
-----

* Add experimental support for Python >= 3.4
* Python apps:
  - The platform name (used for differentiating virtualenvs) now comes
    from yodeploy's settings: `artifacts.platform`.
  - virtualenvs are built with `pip`.
* `TomcatServlet`:
  - Drop Tomcat 6 support.
  - Add (preliminary) Tomcat 8 support.
  - Append `.conf` to vhosts (cleaning up old vhosts in the process).
* `UpstartApp` and `SupervisordApp`: Replaced with `DaemonApp`, which
  behaves identically, and will use the same templates.
* Internal API changes to `yodeploy.virtualenv`:
  - `ve_version()` is replaced with `ve_id()`.
  - `create_ve()` requires a `platform` argument.
* Internal API changes to `yodeploy.repository` repositories:
  - `.get()` always returns byte buffers
  - `put()` accept unicode strings, unicode buffers, byte strings, and
     byte buffers.
* test suite: suffix test-data dir with python version data to avoid
  cross-environment collisions when running the test suite with cached data
* test suite: Install a copy of the current yodeploy checkout (in
  whatever state it's in) into the test virtualenv rather than the latest
  version from the configured package index
* test suite: Ensure that the test process does not hang indefinitely due to
  ThreadedLogStreamServer failures.

0.7.3
-----

* NOTE: From now YoDeploy requires Python >= 2.7.
* Make `hooks.django.DjangoApp.manage_py` method return command output.


0.7.2
-----

* Add Django 1.9+ compatibility for `migrate` command (`syncdb` still works
  for Django 1.6 and lower)

0.7.1
------

* Make easy_install unzip eggs (the same behavious as before yodeploy 0.7.0)

0.7.0
------

* Bump to newer version of setuptools

0.6.0
------

* `uses_south` flag in DjangoApp hook is renamed to `has_migrations` to be
  compliant with Django 1.8+, which doesn't need South for migrations.

0.5.1
------

* Update manifest

0.5.0
------

* Add `ApacheHostedApp` for single domain apps
* Add `ApacheMultiSiteApp` for whitelabel apps
* Add `DjangoMultiSiteApp` for whitelabel django apps
* `DjangoApp`:
    - Extend `ApacheHostedApp`
    - Add support for celery log
    - Drop support for `vhost-snippet.conf.template`
* Add integration tests with sample apps

0.4.24
------

* Add support for injecting public configuration into a src file
* Bugfix target_url with build artifact
* Add integration tests with sample apps

0.4.23
------

* Update build_artifact and deploy configurator to write a public configuration

0.4.22
------

* Update yoconfigurator to 0.4.6, getting whitespace cleanup and support
  for public configuration.

0.4.21
------

* Migrate writes out to a log file, ensure that the log file exists before
  trying to migrate

0.4.20
------

* Ensure that the log file directory exists before creating the log file

0.4.19
------

* Update `deploy` to not tell campfire

0.4.18
------

* Add support of htpasswd groups with seeded passwords

0.4.17
------

* Stop chown_r breaking on dangling symlinks

0.4.16
------

* Add a data_dir `@property` to the DataDirApp hook so it can be used elsewhere
* Update yoconfigurator to 0.4.4

0.4.15
------

* Support `build-virtualenv -r dev_requirements.txt`
* Add `gc` actions to `spade` and `deploy`.
* Lock shared directories during deploy.

0.4.14
------

* Address the database_migration_class object correctly.

0.4.13
------

* BROKEN - Address the database_migration_class object correctly.

0.4.12
------

* Update `delete_dir_content` to handle missing files

0.4.11
------

* Deploy tomcat7 apps for the first time, without breaking.
* Allow overriding None in deploy configs (yoconfigurator 0.4.3)

0.4.10
------

* Add `delete_dir_content` to util

0.4.8
-----

* Undeploy old versions in Tomcat 7.
  (On Ubuntu 12.04, requires tomcat7 from the Yola PPA)

0.4.6
-----

* Zero-downtime deployment to tomcat.

0.4.5
-----

* Added the `yoconfigurator.app` key to deployconfigs.
  (yoconfigurator 0.4.0)

0.4.4
-----

* Bug fix for the Tomcat hook.

0.4.3
-----

* Write the Apache vhost in the Tomcat hook.

0.4.2
-----

* Added the Tomcat hook.

0.4.1
-----

* `AuthenticatedApp`: Get api_seed from `config.common`.

0.4.0
-----

* Renamed to yodeploy.
* Uses yoconfigurator 0.3.0.

0.3.1-0.3.3
-----------

* Bug fixes.

0.3.0
-----

* Backwards-incompatible repository layout change.
* configs now always come from the master branch/target.

0.2.7
-----

* Added supervisord hook.

0.2.5-0.2.6
-----------

* Only bug fixes.

0.2.4
-----

* Allows re-deploying live versions.
* Adds `UpstartApp`.
* Squashes file ownership to root.
* Reads the YolaPI URL from deploy_settings.

0.2.3
-----

* `ConfiguratedApp`: Use deployconfigs overrides dropped in by Chef.

0.2.2
-----

* `DjangoApp`: Bug fix for virtualhost snippets for services.

0.2.1
-----

* `DjangoApp`: ``collectstatic`` is no longer run by default. Set the
  ``has_static`` attribute to run it.

0.2.0
-----

* `DjangoApp`:

  - The ``vhost_path`` and ``vhost_snippet_path`` are configurable via
    class attributes.
  - Virtualhost snippets for services can be named
    ``deploy/templates/apache2/vhost-snippet.conf.template``.
  - If the ``compile_i18n`` attribute is set, ``compilemessages`` will
    be run during preparation.

0.1
---

* Initial release.
