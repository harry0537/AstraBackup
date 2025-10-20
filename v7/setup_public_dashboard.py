#!/usr/bin/env python3
"""
Setup public dashboard access for managed server
"""

import requests
import subprocess
import json
import os
from flask import Flask

def get_public_ip():
    """Get the public IP address of the server"""
    try:
        # Try multiple services to get public IP
        services = [
            'https://api.ipify.org',
            'https://ipinfo.io/ip',
            'https://ifconfig.me/ip',
            'https://checkip.amazonaws.com'
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    public_ip = response.text.strip()
                    print(f"[OK] Public IP: {public_ip}")
                    return public_ip
            except:
                continue
        
        print("[ERROR] Could not determine public IP")
        return None
    except Exception as e:
        print(f"[ERROR] Error getting public IP: {e}")
        return None

def get_local_ip():
    """Get local IP address"""
    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
        if result.returncode == 0:
            local_ip = result.stdout.strip().split()[0]
            print(f"[OK] Local IP: {local_ip}")
            return local_ip
        else:
            print("[ERROR] Could not determine local IP")
            return None
    except Exception as e:
        print(f"[ERROR] Error getting local IP: {e}")
        return None

def check_firewall():
    """Check if firewall is blocking port 8081"""
    try:
        result = subprocess.run(['ufw', 'status'], capture_output=True, text=True)
        if result.returncode == 0:
            if '8081' in result.stdout:
                print("[INFO] Port 8081 found in firewall rules")
            else:
                print("[WARNING] Port 8081 not found in firewall rules")
                print("You may need to open port 8081:")
                print("sudo ufw allow 8081")
        else:
            print("[INFO] UFW not available or not running")
    except:
        print("[INFO] Could not check firewall status")

def update_config(public_ip, local_ip):
    """Update configuration with public IP"""
    config_file = "rover_config_v7.json"
    
    # Load existing config
    config = {}
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except:
            pass
    
    # Update with public IP information
    config['public_ip'] = public_ip
    config['local_ip'] = local_ip
    config['dashboard_public_url'] = f"http://{public_ip}:8081"
    config['dashboard_local_url'] = f"http://{local_ip}:8081"
    
    # Save updated config
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"[OK] Configuration updated with public IP: {public_ip}")
    return config

def test_dashboard_access(ip, port=8081):
    """Test if dashboard is accessible on given IP"""
    try:
        response = requests.get(f"http://{ip}:{port}", timeout=5)
        if response.status_code == 200:
            print(f"[OK] Dashboard accessible at http://{ip}:{port}")
            return True
        else:
            print(f"[WARNING] Dashboard returned status {response.status_code} at http://{ip}:{port}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Cannot connect to dashboard at http://{ip}:{port}")
        return False
    except Exception as e:
        print(f"[ERROR] Error testing dashboard: {e}")
        return False

def main():
    """Main setup function"""
    print("=" * 60)
    print("PROJECT ASTRA NZ - PUBLIC DASHBOARD SETUP")
    print("=" * 60)
    
    # Get IP addresses
    print("\n[1/4] Getting IP addresses...")
    public_ip = get_public_ip()
    local_ip = get_local_ip()
    
    if not public_ip:
        print("[ERROR] Could not determine public IP")
        return
    
    # Check firewall
    print("\n[2/4] Checking firewall...")
    check_firewall()
    
    # Update configuration
    print("\n[3/4] Updating configuration...")
    config = update_config(public_ip, local_ip)
    
    # Test dashboard access
    print("\n[4/4] Testing dashboard access...")
    print("Testing local access...")
    local_ok = test_dashboard_access(local_ip)
    
    print("Testing public access...")
    public_ok = test_dashboard_access(public_ip)
    
    # Summary
    print("\n" + "=" * 60)
    print("SETUP SUMMARY")
    print("=" * 60)
    print(f"Public IP: {public_ip}")
    print(f"Local IP: {local_ip}")
    print(f"Dashboard Public URL: http://{public_ip}:8081")
    print(f"Dashboard Local URL: http://{local_ip}:8081")
    print()
    print("Access Status:")
    print(f"  Local Access: {'✓' if local_ok else '✗'}")
    print(f"  Public Access: {'✓' if public_ok else '✗'}")
    
    if not public_ok:
        print("\nTroubleshooting steps:")
        print("1. Check if dashboard is running: python3 telemetry_dashboard_v7.py")
        print("2. Open firewall port: sudo ufw allow 8081")
        print("3. Check server security groups (if using cloud provider)")
        print("4. Verify dashboard is binding to 0.0.0.0:8081")
    
    print(f"\nTo access from Windows:")
    print(f"Open browser to: http://{public_ip}:8081")

if __name__ == "__main__":
    main()
