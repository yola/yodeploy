Change Log
==========

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

* Add a data_dir @property to the DataDirApp hook so it can be used elsewhere
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
