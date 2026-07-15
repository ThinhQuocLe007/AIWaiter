from setuptools import setup
import os
from glob import glob

package_name = 'turtlebot4_python_tutorials'

setup(
    name=package_name,
    version='1.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='rkreinin',
    maintainer_email='rkreinin@clearpathrobotics.com',
    description='TurtleBot 4 Python Tutorials',
    license='Apache 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'food_delivery = turtlebot4_python_tutorials.food_delivery:main',
            'pose_aruco_debug = turtlebot4_python_tutorials.pose_aruco_debug:main',
        ],
    },
)
