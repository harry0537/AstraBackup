import subprocess
import sys


def ensure_package(pkg_name: str, import_name: str = None) -> bool:
    mod = import_name or pkg_name
    try:
        __import__(mod)
        return True
    except Exception:
        try:
            print(f"Installing missing package: {pkg_name}…")
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', pkg_name])
            if result.returncode == 0:
                __import__(mod)
                return True
        except Exception:
            return False
    return False


def ensure_dependencies() -> bool:
    ok = True
    ok &= ensure_package('rplidar-roboticia', 'rplidar')
    ok &= ensure_package('pymavlink')
    ok &= ensure_package('numpy')
    # RealSense optional
    try:
        __import__('pyrealsense2')
    except Exception:
        pass
    return ok


