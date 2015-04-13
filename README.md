yodeploy
========
[![Build Status](https://jenkins.yola.net/buildStatus/icon?job=Build-yodeploy)](https://jenkins.yola.net/view/Build/job/Build-yodeploy/)

Python helpers for Yola's Deployment system.

Using the hooks
---------------

Hooks are specified in `deploy/hooks.py` in the application, as the
variable `hook`. It should be a class, implementing the interface
`yodeploy.hooks.base.DeployHook`.

`yodeploy.hooks` includes a set of more useful hook classes, useful
for subclassing or using as-is:

    `yodeploy.hooks.python.PythonApp`:
        All your virtualenv needs. Declare requirements in
        `requirements.txt` in the root of your application.
        A directory named `virtualenv` will be created in the
        application's directory.

The current hook points are:

    `prepare`:
        Post-unpack, but before the `live` symlink is swung.

    `deployed`:
        After the symlink is swung.

On-disk Deployment layout
-------------------------

*/srv/app*: Deploy root

    `versions`

        *hash*: Each unpacked version of the application

        `unpack`: Working area

    `live`: Symlink to `versions/`\ *live-version*.

    `virtualenvs`

        *hash*: Each unpacked virtualenv (symlinked to from the unpacked
        application)

        `unpack`: Working area

Repository layout
-----------------

*app/target/artifact/version* : A particular version of an
artifact.

*app/target/artifact/version*.meta: The metadata for an
artifact. Only used in stores that don't support metadata on objects.

*app/target/artifact*/latest: A text file containing
the *version* of the most recent *artifact*.

Compat levels
-------------

Artifacts have a 'deploy_compat' attribute, defining the deployment
system they were designed for. It is defined in `deploy/compat` in the
source.

1. Yola's legacy deployment system (Duncan Deploy)
2. The legacy repository with yola.deploy < 0.3
3. yola.deploy 0.3.x.
4. yodeploy >= 0.4 (after the rename).

Building and uploading
----------------------

You can upload this to yolapi by running:

  python setup.py sdist upload -r https://yolapi.yola.net/pypi/


Local Deploy Bootstrap
----------------------

When running `build-virtualenv`, watch output, ensure easy_install does not
downgrade any installed packages:

    Removing suds 0.4.1-htj.yola1   <-- oh no, removing yola specific release
    Adding suds 0.3.9


Testing
-------

Run `nosetests`
