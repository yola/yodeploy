import os


class AttrDict(dict):
    __getattr__ = dict.__getitem__

test_dir = os.path.dirname(__file__)

deploy_settings = AttrDict(

    apps=AttrDict(
        limit=False
    ),

    artifacts=AttrDict(
        store="local",
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
    ),

    paths=AttrDict(
        apps=os.path.join(test_dir, 'filesys', 'deployed')
    ),

    report=AttrDict(
        services={}
    ),

)
