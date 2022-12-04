from setuptools import setup, find_packages


__version__ = "1.0.0"

setup(
    entry_points={
        'console_scripts': [
            'stream-sender = securestream_endpoint.sender:sender_main',
            'stream-receiver = securestream_endpoint.receiver:receiver_main',
            'stream-proxy = securestream_endpoint.proxy:proxy_main',
            'stream-controller = securestream_controller.app:controller_main',
            'stream-rsagen = securestream_endpoint.rsa:rsagen_main',
        ],
    },
    name='securestream',
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
        "requests==2.28.1",
        "egcd==0.4.3"
    ]
)
