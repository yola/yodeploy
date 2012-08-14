yola.deploy
===========

Python helpers for yola's Deployment system.

Using the hooks
---------------

Hooks are specified in `deploy/hooks.py` in the application, as the
variable `hook`. It should be a class, implementing the interface
`yola.deploy.hooks.base.DeployHook`.

`yola.deploy.hooks` includes a set of more useful hook classes, useful
for subclassing or using as-is:

    `yola.deploy.hooks.python.PythonApp`:
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

`/srv/`\ *app*: Deploy root

    `versions`

        *hash*: Each unpacked version of the application

        `unpack`: Working area

    `live`: Symlink to `versions/`\ *live-version*.

    `virtualenvs`

        *hash*: Each unpacked virtualenv (symlinked to from the unpacked
        application)

        `unpack`: Working area

Building and uploading
----------------------

If you have not bumped the version, you will need to remove the files and
current version here: https://yolapi.yola.net/pypi/yola.deploy/manage/versions/

Either way, you can upload this to yolapi by running:

  python setup.py sdist upload -r https://yolapi.yola.net/pypi/

