#!/usr/bin/env python3

"""
Setup configuration for tarkbot_robot ROS2 Python package.
"""

from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'tarkbot_robot'

setup(
    name=package_name,
    version='2.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch',
            glob(os.path.join('launch', '*.launch.py'))),
        ('share/' + package_name + '/launch/navigation',
            glob(os.path.join('launch/navigation', '*.launch.py'))),
        ('share/' + package_name + '/launch/slam',
            glob(os.path.join('launch/slam', '*.launch.py'))),
        # *.yaml = EKF / Nav2 / RTAB-Map tuning; floorplan.json = table + dock waypoints (the
        # backend reads the copy in the source tree, visual_delivery this installed one — one
        # file, so they cannot drift apart).
        ('share/' + package_name + '/config',
            glob(os.path.join('config', '*.yaml')) + glob(os.path.join('config', '*.json'))),
        ('share/' + package_name + '/rviz',
            glob(os.path.join('rviz', '*.rviz'))),
        ('share/' + package_name + '/urdf',
            glob(os.path.join('urdf', '*.urdf'))),
    ],
    install_requires=['setuptools', 'pyserial'],
    zip_safe=True,
    maintainer='XTARK',
    maintainer_email='xtark@xtark.cn',
    description='TarkBot R20 Robot ROS2 Python Driver',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            f'robot_node = {package_name}.robot_node:main',
            f'path_publisher = {package_name}.path_publisher:main',
            f'monitor_ekf = {package_name}.monitor_ekf:main',
            f'aruco_debug = {package_name}.aruco_debug:main',
            f'pose_record = {package_name}.pose_record:main',
            f'deliver_test = {package_name}.deliver_test:main',
        ],
    },
)
