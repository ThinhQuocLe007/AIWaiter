from setuptools import setup
import os
from glob import glob

package_name = 'ai_waiter_ros'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.sdf')),
    ] + [
        (os.path.join('share', package_name, os.path.dirname(p)), [p])
        for p in glob('models/**/*', recursive=True)
        if os.path.isfile(p)
    ],

    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='your_name',
    description='Simulation assets for AI Waiter',
    license='Apache-2.0',
    entry_points={'console_scripts': []},
)
