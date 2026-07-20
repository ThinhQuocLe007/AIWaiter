#!/usr/bin/env python3

"""
Serial Communication Module for TarkBot Robot.
Handles X-Protocol communication with OpenCTR board.

X-Protocol Frame Format (for 20-byte sensor data, total 25 bytes):
- Byte 0: Header 0xAA
- Byte 1: Header 0x55
- Byte 2: Frame length = data_len + 5 (e.g. 25 for 20-byte data)
- Byte 3: Command ID (e.g. 0x10 for sensor data)
- Bytes 4..(4+data_len-1): Data payload
- Last byte: Checksum (sum of all preceding bytes, lower 8 bits)

Data Payload (20 bytes):
- Bytes 0-5: Accelerometer data (ACC_X, ACC_Y, ACC_Z) [int16 * 3]
- Bytes 6-11: Gyroscope data (GYRO_X, GYRO_Y, GYRO_Z) [int16 * 3]
- Bytes 12-17: Velocity data (VEL_X, VEL_Y, VEL_W) [int16 * 3]
- Bytes 18-19: Battery voltage [uint16]

Copyright 2022-2024 XTARK ROBOTIS CO., LTD.
Licensed under the Apache License, Version 2.0 (the "License")
"""

import serial
import struct
import threading
from typing import Callable, Optional, Tuple
import time


class SerialProtocol:
    """X-Protocol implementation for robot communication."""

    # Protocol frame markers and IDs
    FRAME_HEADER_1 = 0xAA
    FRAME_HEADER_2 = 0x55
    FRAME_LENGTH = 20

    # Command IDs from OpenCTR to ROS
    ID_CTR2ROS_DATA = 0x10  # Comprehensive sensor data from controller
    
    # Command IDs from ROS to OpenCTR (for future use)
    ID_ROS2CTR_VEL = 0x50    # Velocity command
    ID_ROS2CTR_IMU = 0x51    # IMU calibration
    ID_ROS2CTR_RTY = 0x5A    # Robot type parameter
    ID_ROS2CTR_LGT = 0x52    # Light debug data
    ID_ROS2CTR_LST = 0x53    # Light save data
    ID_ROS2CTR_BEEP = 0x54   # Beeper control



    def __init__(self, port: str, baud_rate: int):
        """
        Initialize serial protocol handler.
        
        Args:
            port: Serial port name (from node parameter, e.g. robot.yaml)
            baud_rate: Serial baud rate (from node parameter)
        """
        self.port = port
        self.baud_rate = baud_rate
        self.serial_port: Optional[serial.Serial] = None
        self.is_connected = False
        self.receive_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Receive buffer
        self.rx_buffer = bytearray()
        self.rx_state = 0  # State machine for frame parsing
        self.rx_frame_data = bytearray()
        self.rx_checksum = 0
        
        # Callback for received payload data
        self.data_callback: Optional[Callable] = None
        # Optional callback for full validated frame bytes (header..checksum)
        self.raw_frame_callback: Optional[Callable[[bytes], None]] = None

    def open(self) -> bool:
        """
        Open serial port connection.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE,
                timeout=1.0
            )
            self.is_connected = True
            return True
        except Exception as e:
            print(f"Failed to open serial port {self.port}: {e}")
            self.is_connected = False
            return False

    def close(self):
        """Close serial port connection."""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=2.0)
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.is_connected = False

    def start_receive(self, callback: Callable):
        """
        Start receiving and parsing serial data.
        
        Args:
            callback: Callback function to handle received data frame
        """
        self.data_callback = callback
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()

    def set_raw_frame_callback(self, callback: Optional[Callable[[bytes], None]]):
        """Set optional callback to receive complete validated frames as raw bytes."""
        self.raw_frame_callback = callback

    def _receive_loop(self):
        """Main receive loop - runs in separate thread."""
        while self.running and self.is_connected:
            try:
                if self.serial_port and self.serial_port.in_waiting > 0:
                    num_bytes = self.serial_port.in_waiting
                    byte_data = self.serial_port.read(num_bytes)
                    if byte_data:
                        for byte_val in byte_data:
                            self._parse_frame(byte_val)
                else:
                    time.sleep(0.001)  # Small sleep to prevent busy waiting
            except Exception as e:
                print(f"Error in receive loop: {e}")
                time.sleep(0.1)

    def _parse_frame(self, byte_val: int):
        """
        Parse incoming byte using state machine.
        
        X-Protocol frame format:
        [0xAA][0x55][Length][...Data...][Checksum]
        
        Args:
            byte_val: Single byte from serial port
        """
        if self.rx_state == 0:  # Waiting for first header byte (0xAA)
            if byte_val == self.FRAME_HEADER_1:
                self.rx_frame_data = bytearray([byte_val])
                self.rx_state = 1
        elif self.rx_state == 1:  # Waiting for second header byte (0x55)
            if byte_val == self.FRAME_HEADER_2:
                self.rx_frame_data.append(byte_val)
                self.rx_checksum = self.FRAME_HEADER_1 + self.FRAME_HEADER_2
                self.rx_state = 2
            else:
                self.rx_state = 0  # Reset if invalid
        elif self.rx_state == 2:  # Waiting for length byte
            self.rx_frame_data.append(byte_val)
            frame_length = byte_val
            self.rx_checksum += byte_val
            self.rx_state = 3
            # Remaining bytes = frame_length - 4 (subtract header(2) + length(1) + checksum(1))
            self.bytes_to_receive = frame_length - 4
        elif self.rx_state == 3:  # Receiving data and command ID
            self.rx_frame_data.append(byte_val)
            self.rx_checksum += byte_val
            self.bytes_to_receive -= 1
            if self.bytes_to_receive == 0:
                self.rx_state = 4
        elif self.rx_state == 4:  # Receiving checksum
            if byte_val == (self.rx_checksum & 0xFF):
                if self.raw_frame_callback:
                    self.raw_frame_callback(bytes(self.rx_frame_data + bytearray([byte_val])))
                # Frame valid - extract and process data
                self._process_frame(self.rx_frame_data)
            else:
                pass  # Checksum mismatch, discard frame
            # Reset for next frame
            self.rx_state = 0
            self.rx_frame_data = bytearray()

    def _process_frame(self, frame_data: bytearray):
        """
        Process a complete and valid frame.
        
        Args:
            frame_data: Complete frame data without checksum
        """
        if len(frame_data) < 4:
            return

        # Extract frame components
        command_id = frame_data[3]
        payload = bytes(frame_data[4:])  # Data after command ID

        # Only process controller-to-ROS data
        if command_id == self.ID_CTR2ROS_DATA and len(payload) >= 20:
            if self.data_callback:
                self.data_callback(payload)

    def send_command(self, data: bytes, cmd_id: int = ID_ROS2CTR_VEL) -> bool:
        """
        Send command packet to OpenCTR board.
        
        Args:
            data: Data bytes to send
            cmd_id: Command ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected or not self.serial_port:
            return False

        try:
            # Build frame: [Header1][Header2][FrameLen][CmdID][Data...][Checksum]
            frame_data = bytearray()
            frame_data.append(self.FRAME_HEADER_1)
            frame_data.append(self.FRAME_HEADER_2)
            # Frame length = header(2) + length(1) + cmdID(1) + data + checksum(1)
            frame_length = len(data) + 5
            frame_data.append(frame_length)
            frame_data.append(cmd_id)
            frame_data.extend(data)

            # Calculate checksum: sum of all bytes before checksum
            checksum = 0
            for b in frame_data:
                checksum += b
            checksum &= 0xFF  # Keep only lower 8 bits

            frame_data.append(checksum)

            # Send to serial port
            self.serial_port.write(frame_data)
            return True

        except Exception as e:
            print(f"Failed to send command: {e}")
            return False

    def send_velocity_command(self, vx: float, vy: float, vw: float) -> bool:
        """
        Send velocity command to robot.
        
        Args:
            vx: Linear velocity in X direction (m/s)
            vy: Linear velocity in Y direction (m/s)
            vw: Angular velocity around Z axis (rad/s)
            
        Returns:
            True if successful, False otherwise
        """
        # Convert float velocities to int16 (scale by 1000 to preserve precision)
        vx_int = int(vx * 1000) & 0xFFFF
        vy_int = int(vy * 1000) & 0xFFFF
        vw_int = int(vw * 1000) & 0xFFFF

        # Pack into 6 bytes (big-endian)
        data = bytearray()
        data.append((vx_int >> 8) & 0xFF)
        data.append(vx_int & 0xFF)
        data.append((vy_int >> 8) & 0xFF)
        data.append(vy_int & 0xFF)
        data.append((vw_int >> 8) & 0xFF)
        data.append(vw_int & 0xFF)

        return self.send_command(bytes(data), self.ID_ROS2CTR_VEL)

    def send_stop_command(self) -> bool:
        """Send stop command to robot."""
        return self.send_velocity_command(0.0, 0.0, 0.0)

    def send_beep_command(self, duration_ms: int = 100) -> bool:
        """
        Send beep command to robot.
        
        Args:
            duration_ms: Beep duration in milliseconds
            
        Returns:
            True if successful, False otherwise
        """
        data = bytes([duration_ms & 0xFF])
        return self.send_command(data, self.ID_ROS2CTR_BEEP)

    def send_robot_type(self, robot_type: str) -> bool:
        """
        Send robot type to controller.
        
        Args:
            robot_type: Robot type string (e.g., "r20_mec", "r20_fwd", "r20_akm", etc.)
            
        Returns:
            True if successful, False otherwise
        """
        # Map robot type to controller code
        type_map = {
            "r20_mec": 1,   # Mecanum wheels
            "r20_fwd": 2,   # Forward wheels
            "r20_akm": 3,   # Ackermann steering
            "r20_twd": 4,   # Two-wheel differential
            "r20_tak": 5,   # Tank track
            "r20_omni": 6,  # Omni wheels
        }
        
        type_code = type_map.get(robot_type.lower(), 1)
        data = bytes([type_code & 0xFF])
        return self.send_command(data, self.ID_ROS2CTR_RTY)
