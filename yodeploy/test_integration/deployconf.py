import os
import sysconfig


class AttrDict(dict):
    __getattr__ = dict.__getitem__

test_dir = os.path.dirname(__file__)

deploy_settings = AttrDict(

    apps=AttrDict(
        limit=False
    ),

    artifacts=AttrDict(
        cluster='',
        store="local",
        platform=sysconfig.get_platform(),
        store_settings=AttrDict(
            local=AttrDict(
                directory=os.path.join(test_dir, 'filesys', 'artifacts')
            ),
        ),
        environment=""
    ),

    build=AttrDict(
        deploy_content_server='',
        environment='',
        cluster='',
        github=AttrDict(
            report=False,
        ),
        configs_dir='',
        pypi=None,
    ),

    deployconfigs=AttrDict(
        overrides=[],
    ),

    paths=AttrDict(
        apps=os.path.join(test_dir, 'filesys', 'deployed')
    ),

    report=AttrDict(
        services={}
    ),

    server=AttrDict(
        username='test',
        password='password',
    )

)
