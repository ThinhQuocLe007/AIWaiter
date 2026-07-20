#!/usr/bin/env python3

"""
Data Conversion Module for TarkBot Robot.
Converts raw sensor data from OpenCTR board to SI units and ROS message types.

Data Payload Structure (20 bytes):
- Bytes 0-1: ACC_X (int16)
- Bytes 2-3: ACC_Y (int16)
- Bytes 4-5: ACC_Z (int16)
- Bytes 6-7: GYRO_X (int16)
- Bytes 8-9: GYRO_Y (int16)
- Bytes 10-11: GYRO_Z (int16)
- Bytes 12-13: Velocity X (int16, scaled by 1000)
- Bytes 14-15: Velocity Y (int16, scaled by 1000)
- Bytes 16-17: Velocity W (int16, scaled by 1000)
- Bytes 18-19: Battery voltage (uint16, scaled by 100)

Copyright 2022-2024 XTARK ROBOTIS CO., LTD.
Licensed under the Apache License, Version 2.0 (the "License")
"""

import struct
import math
from dataclasses import dataclass
from typing import Tuple


@dataclass
class IMUData:
    """IMU sensor data structure."""
    acc_x: float  # m/s²
    acc_y: float  # m/s²
    acc_z: float  # m/s²
    gyro_x: float  # rad/s
    gyro_y: float  # rad/s
    gyro_z: float  # rad/s


@dataclass
class VelocityData:
    """Robot velocity data structure."""
    linear_x: float  # m/s
    linear_y: float  # m/s
    angular_z: float  # rad/s


@dataclass
class BatteryData:
    """Battery voltage data structure."""
    voltage: float  # Volts


@dataclass
class RobotSensorData:
    """Complete robot sensor data."""
    imu: IMUData
    velocity: VelocityData
    battery: BatteryData
    timestamp: float  # Seconds


class DataConverter:
    """
    Converts raw bytes from OpenCTR board to SI units.
    
    Calibration constants based on OpenCTR_H60V32_R20_1024_V3.01:
    - IMU Accelerometer: ±2g range, 16-bit signed
    - IMU Gyroscope: ±500°/s range, 16-bit signed
    """

    # IMU conversion constants
    # Accelerometer: ±2g range, range = ±32768
    # Conversion: (2*9.8)/32768 = 0.000598... m/s² per unit
    ACC_RATIO = (2.0 * 9.8) / 32768.0

    # Gyroscope: ±500°/s range, range = ±32768
    # Conversion: (500 * π / 180) / 32768 = 0.000266... rad/s per unit
    GYRO_RATIO = (500.0 * math.pi / 180.0) / 32768.0

    # Velocity conversion: stored as int16 scaled by 1000
    VELOCITY_SCALE = 1000.0

    # Battery voltage conversion: stored as uint16 scaled by 100
    BATTERY_SCALE = 100.0

    def __init__(self):
        """Initialize data converter."""
        pass

    @staticmethod
    def _unpack_int16(data: bytes, offset: int) -> int:
        """
        Unpack signed 16-bit integer from bytes.
        
        Args:
            data: Byte array
            offset: Starting position
            
        Returns:
            Signed 16-bit integer value
        """
        return struct.unpack('>h', data[offset:offset + 2])[0]

    @staticmethod
    def _unpack_uint16(data: bytes, offset: int) -> int:
        """
        Unpack unsigned 16-bit integer from bytes.
        
        Args:
            data: Byte array
            offset: Starting position
            
        Returns:
            Unsigned 16-bit integer value
        """
        return struct.unpack('>H', data[offset:offset + 2])[0]

    def parse_sensor_data(self, payload: bytes, timestamp: float = 0.0) -> RobotSensorData:
        """
        Parse raw sensor payload from OpenCTR board.
        
        Args:
            payload: 20-byte payload containing sensor data
            timestamp: Timestamp in seconds (default: 0.0)
            
        Returns:
            RobotSensorData object with all parsed and converted data
            
        Raises:
            ValueError: If payload is not exactly 20 bytes
        """
        if len(payload) != 20:
            raise ValueError(f"Expected 20-byte payload, got {len(payload)} bytes")

        # Parse raw sensor values (big-endian int16)
        acc_x_raw = self._unpack_int16(payload, 0)
        acc_y_raw = self._unpack_int16(payload, 2)
        acc_z_raw = self._unpack_int16(payload, 4)

        gyro_x_raw = self._unpack_int16(payload, 6)
        gyro_y_raw = self._unpack_int16(payload, 8)
        gyro_z_raw = self._unpack_int16(payload, 10)

        vel_x_raw = self._unpack_int16(payload, 12)
        vel_y_raw = self._unpack_int16(payload, 14)
        vel_w_raw = self._unpack_int16(payload, 16)

        bat_vol_raw = self._unpack_uint16(payload, 18)

        # Convert to SI units
        imu_data = self._convert_imu_data(acc_x_raw, acc_y_raw, acc_z_raw,
                                          gyro_x_raw, gyro_y_raw, gyro_z_raw)

        velocity_data = self._convert_velocity_data(vel_x_raw, vel_y_raw, vel_w_raw)

        battery_data = self._convert_battery_data(bat_vol_raw)

        return RobotSensorData(
            imu=imu_data,
            velocity=velocity_data,
            battery=battery_data,
            timestamp=timestamp
        )

    def _convert_imu_data(self, acc_x_raw: int, acc_y_raw: int, acc_z_raw: int,
                          gyro_x_raw: int, gyro_y_raw: int, gyro_z_raw: int) -> IMUData:
        """
        Convert raw IMU data to SI units.

        OpenCTR firmware already remaps IMU axes to ROS conventions before
        sending payload bytes, so no extra axis transform is applied here.
        """
        # Convert raw values to physical units
        acc_x_ctv = acc_x_raw * self.ACC_RATIO
        acc_y_ctv = acc_y_raw * self.ACC_RATIO
        acc_z_ctv = acc_z_raw * self.ACC_RATIO

        gyro_x_ctv = gyro_x_raw * self.GYRO_RATIO
        gyro_y_ctv = gyro_y_raw * self.GYRO_RATIO
        gyro_z_ctv = gyro_z_raw * self.GYRO_RATIO

        return IMUData(
            acc_x=acc_x_ctv,
            acc_y=acc_y_ctv,
            acc_z=acc_z_ctv,
            gyro_x=gyro_x_ctv,
            gyro_y=gyro_y_ctv,
            gyro_z=gyro_z_ctv
        )

    def _convert_velocity_data(self, vel_x_raw: int, vel_y_raw: int,
                               vel_w_raw: int) -> VelocityData:
        """
        Convert raw velocity data to SI units.
        
        Raw values are stored as int16 scaled by 1000.
        Unit: m/s for linear velocities, rad/s for angular velocity
        """
        vel_x = vel_x_raw / self.VELOCITY_SCALE
        vel_y = vel_y_raw / self.VELOCITY_SCALE
        vel_w = vel_w_raw / self.VELOCITY_SCALE

        return VelocityData(
            linear_x=vel_x,
            linear_y=vel_y,
            angular_z=vel_w
        )

    def _convert_battery_data(self, bat_vol_raw: int) -> BatteryData:
        """
        Convert raw battery voltage to Volts.
        
        Raw value is stored as uint16 scaled by 100.
        Unit: Volts
        """
        voltage = bat_vol_raw / self.BATTERY_SCALE

        return BatteryData(voltage=voltage)

    def calculate_imu_quaternion(self, gx: float, gy: float, gz: float,
                                  ax: float, ay: float, az: float,
                                  dt: float = 0.02,
                                  q_prev: Tuple[float, float, float, float] = None
                                  ) -> Tuple[float, float, float, float]:
        """
        Calculate orientation quaternion using Mahony AHRS filter.
        Matches the C implementation in tarkbot_robot ROS1 (calculateImuQuaternion).

        Uses proportional correction from accelerometer gravity reference
        applied to gyroscope rates before quaternion integration.

        Args:
            gx, gy, gz: Angular velocity from gyroscope (rad/s)
            ax, ay, az: Acceleration from accelerometer (m/s²)
            dt: Time step (seconds)
            q_prev: Previous quaternion [w, x, y, z] (default: identity)

        Returns:
            Quaternion as (w, x, y, z) tuple
        """
        if q_prev is None:
            q_prev = (1.0, 0.0, 0.0, 0.0)

        q0, q1, q2, q3 = q_prev  # w, x, y, z

        # Normalize accelerometer to unit vector
        a_norm = math.sqrt(ax*ax + ay*ay + az*az)
        if a_norm < 1e-6:
            a_norm = 1.0
        ax /= a_norm
        ay /= a_norm
        az /= a_norm

        # Estimated gravity direction from quaternion (half-values, matching C code)
        halfvx = q1 * q3 - q0 * q2
        halfvy = q0 * q1 + q2 * q3
        halfvz = q0 * q0 - 0.5 + q3 * q3

        # Error: cross product of measured and estimated gravity
        halfex = ay * halfvz - az * halfvy
        halfey = az * halfvx - ax * halfvz
        halfez = ax * halfvy - ay * halfvx

        # Apply proportional feedback to gyro rates (twoKp = 1.0 matching C code)
        two_kp = 1.0
        gx += two_kp * halfex
        gy += two_kp * halfey
        gz += two_kp * halfez

        # Pre-multiply common factors
        gx *= 0.5 * dt
        gy *= 0.5 * dt
        gz *= 0.5 * dt

        # Integrate quaternion rate of change
        qa, qb, qc = q0, q1, q2
        q0 += (-qb * gx - qc * gy - q3 * gz)
        q1 += ( qa * gx + qc * gz - q3 * gy)
        q2 += ( qa * gy - qb * gz + q3 * gx)
        q3 += ( qa * gz + qb * gy - qc * gx)

        # Normalize quaternion
        q_norm = math.sqrt(q0*q0 + q1*q1 + q2*q2 + q3*q3)
        if q_norm < 1e-6:
            q_norm = 1.0

        return (q0/q_norm, q1/q_norm, q2/q_norm, q3/q_norm)
