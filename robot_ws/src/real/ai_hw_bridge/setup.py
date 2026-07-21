import os
from glob import glob

from setuptools import setup

package_name = 'ai_hw_bridge'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Table/dock waypoints. The backend reads the copy in the source tree, the robot reads
        # this installed copy — one file, so they cannot drift apart.
        (os.path.join('share', package_name, 'config'), glob('config/*.json')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ducduy',
    maintainer_email='ducduy9304@gmail.com',
    description='AI Waiter real-robot bridge: dispatcher tasks -> tarkbot Nav2 motion + '
                'map-frame heartbeats for the panel minimap.',
    license='Apache 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'task_bridge = ai_hw_bridge.task_bridge:main',
        ],
    },
)
