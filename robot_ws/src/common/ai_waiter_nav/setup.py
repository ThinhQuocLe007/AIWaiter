from setuptools import setup
import os
from glob import glob

package_name = 'ai_waiter_nav'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'maps'), glob('maps/*')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*')),
        (os.path.join('share', package_name, 'config'), glob('config/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='lequocthinh',
    maintainer_email='lequocthinh@todo.todo',
    description='Navigation and simulation assets for AI Waiter project',
    license='Apache-2.0',
    tests_require=[],
    entry_points={
        'console_scripts': [
        ],
    },
)
