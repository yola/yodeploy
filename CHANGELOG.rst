Change Log
==========

0.2.5
-----

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
