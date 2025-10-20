#!/usr/bin/env python3
"""
Test rover connection and dashboard access
"""

import requests
import time
import subprocess
import json

def test_zerotier_connection():
    """Test ZeroTier network connectivity"""
    print("Testing ZeroTier network connectivity...")
    
    # Get ZeroTier network info
    try:
        result = subprocess.run(['zerotier-cli', 'listnetworks'], 
                              capture_output=True, text=True)
        print("ZeroTier networks:")
        print(result.stdout)
        
        # Check if we're connected to the rover network
        if '4753cf475f287023' in result.stdout:
            print("✓ Connected to rover network")
            return True
        else:
            print("✗ Not connected to rover network")
            return False
    except Exception as e:
        print(f"✗ Error checking ZeroTier: {e}")
        return False

def test_rover_ping():
    """Test if rover is reachable"""
    print("\nTesting rover connectivity...")
    
    rover_ip = "172.25.133.85"
    
    try:
        result = subprocess.run(['ping', '-c', '1', rover_ip], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✓ Rover is reachable at {rover_ip}")
            return True
        else:
            print(f"✗ Rover not reachable at {rover_ip}")
            return False
    except Exception as e:
        print(f"✗ Error pinging rover: {e}")
        return False

def test_dashboard_access():
    """Test if dashboard is accessible"""
    print("\nTesting dashboard access...")
    
    dashboard_url = "http://172.25.133.85:8081"
    
    try:
        response = requests.get(dashboard_url, timeout=5)
        if response.status_code == 200:
            print(f"✓ Dashboard accessible at {dashboard_url}")
            print(f"  Response: {response.status_code}")
            return True
        else:
            print(f"✗ Dashboard returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to dashboard at {dashboard_url}")
        print("  Make sure dashboard is running on rover")
        return False
    except Exception as e:
        print(f"✗ Error accessing dashboard: {e}")
        return False

def check_rover_services():
    """Check if rover services are running"""
    print("\nChecking rover services...")
    
    try:
        # Check if rover manager is running
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if 'rover_manager_v7.py' in result.stdout:
            print("✓ Rover manager is running")
        else:
            print("✗ Rover manager not running")
        
        # Check if dashboard is running
        if 'telemetry_dashboard_v7.py' in result.stdout:
            print("✓ Dashboard is running")
        else:
            print("✗ Dashboard not running")
        
        # Check if proximity bridge is running
        if 'combo_proximity_bridge_v7.py' in result.stdout:
            print("✓ Proximity bridge is running")
        else:
            print("✗ Proximity bridge not running")
            
    except Exception as e:
        print(f"✗ Error checking services: {e}")

def main():
    """Main test function"""
    print("=" * 60)
    print("ROVER CONNECTION TEST")
    print("=" * 60)
    
    # Test ZeroTier connection
    zerotier_ok = test_zerotier_connection()
    
    # Test rover ping
    ping_ok = test_rover_ping()
    
    # Test dashboard access
    dashboard_ok = test_dashboard_access()
    
    # Check rover services
    check_rover_services()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"ZeroTier Connection: {'✓' if zerotier_ok else '✗'}")
    print(f"Rover Ping: {'✓' if ping_ok else '✗'}")
    print(f"Dashboard Access: {'✓' if dashboard_ok else '✗'}")
    
    if all([zerotier_ok, ping_ok, dashboard_ok]):
        print("\n🎉 All tests passed! Rover is fully accessible.")
        print(f"Dashboard URL: http://172.25.133.85:8081")
    else:
        print("\n❌ Some tests failed. Check the issues above.")
        print("\nTroubleshooting steps:")
        print("1. Make sure ZeroTier is running and authorized")
        print("2. Start rover services: python3 rover_manager_v7.py")
        print("3. Check firewall settings")

if __name__ == "__main__":
    main()
