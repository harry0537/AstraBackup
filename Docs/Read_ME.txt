# Project Astra NZ

An autonomous navigation system for agricultural and research applications using ArduPilot and modern sensor technologies.

## Overview

This project develops autonomous rover capabilities using ArduPilot firmware with integrated LiDAR and depth camera systems. The platform is designed for precision operation in orchard environments and agricultural settings.

## Key Features

- **Autonomous Navigation**: ArduPilot-based flight control with waypoint missions
- **Obstacle Avoidance**: Real-time detection using LiDAR and depth cameras
- **Row Following**: Precision agriculture navigation for orchard operations
- **Remote Monitoring**: WiFi telemetry with Mission Planner integration
- **Sensor Fusion**: Multi-modal sensor integration for robust operation

## Hardware Platform

- **Flight Controller**: Pixhawk 6C with ArduPilot Rover firmware
- **LiDAR**: SLAMTEC RPLidar S3 for 360° obstacle detection
- **Depth Camera**: Intel RealSense for forward obstacle avoidance
- **Companion Computer**: Ubuntu-based system for sensor processing
- **Communication**: MAVLink over WiFi for ground station connectivity

## Applications

- **Orchard Automation**: Autonomous navigation between crop rows with cloud monitoring
- **Agricultural Surveying**: Precision mapping and monitoring with real-time data upload
- **Fleet Management**: Multi-vehicle coordination via AWS Mission Control Server
- **Research Platforms**: Configurable autonomous vehicle testbed with cloud analytics
- **Environmental Monitoring**: Automated data collection with remote cloud access

## System Architecture

The system combines ArduPilot's proven autopilot capabilities with modern sensor technologies. A companion computer processes LiDAR and camera data, converting it to MAVLink messages for the flight controller. This enables sophisticated obstacle avoidance while maintaining the reliability of ArduPilot's navigation algorithms.

## Getting Started

1. Review hardware requirements and setup documentation
2. Install and configure ArduPilot Rover firmware
3. Set up companion computer with sensor integration scripts
4. Configure ground control station connectivity
5. Set up AWS Mission Control Server integration
6. Calibrate sensors and test basic functionality

## Requirements

- Pixhawk 6C or compatible ArduPilot autopilot
- Ubuntu companion computer
- Mission Planner or compatible ground control software
- SLAMTEC RPLidar S3 and Intel RealSense camera
- WiFi connectivity for telemetry