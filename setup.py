from setuptools import setup, find_packages


__version__ = "1.0.0"

setup(
    entry_points={
        'console_scripts': [
            'comp7005-sender = comp7005endpoint.sender:sender_main',
            'comp7005-reciever = comp7005endpoint.receiver:receiver_main',
            'comp7005-proxy = comp7005endpoint.proxy:proxy_main',
            'comp7005-controller = comp7005controller.app:controller_main',
        ],
    },
    name='comp7005termproject',
    version=__version__,
    packages=find_packages("src"),
    package_dir={'': 'src'},
    url='',
    license='',
    author='bcit',
    author_email='',
    description='',
    dependency_links=[],
    install_requires=[
        "Flask==2.2.2",
        "requests==2.28.1"
    ]
)
