#!/usr/bin/env python3
"""
Armold Bridge Watchdog

Monitors the serial bridge and board connections. Restarts the bridge service
if communication is lost (USB disconnect, board reset, etc).

Checks:
1. Bridge systemd service is running
2. Serial device(s) exist
3. ROS 2 /stepper_state topic is publishing (bridge is alive and connected)

If any check fails, restarts the bridge service and logs the event.
"""

import subprocess
import time
import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [WATCHDOG] %(levelname)s: %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger('armold_watchdog')

# --- Configuration ---
BRIDGE_SERVICE = 'armold-bridge.service'
EINSY_DEVICE = '/dev/armold_einsy'
RAMPS_DEVICE = '/dev/armold_ramps'
CHECK_INTERVAL = 10  # seconds between checks
STALE_TIMEOUT = 15   # seconds before considering state topic stale
MAX_RESTARTS = 5     # max restarts before backing off
BACKOFF_TIME = 60    # seconds to wait after hitting max restarts


def run_cmd(cmd: list[str], timeout: float = 10.0) -> tuple[int, str]:
    """Run a shell command and return (returncode, stdout).

    Args:
        cmd: Command as list of strings.
        timeout: Timeout in seconds.

    Returns:
        Tuple of (return code, stdout string).
    """
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return -1, 'timeout'
    except Exception as e:
        return -1, str(e)


def is_service_active() -> bool:
    """Check if the bridge systemd service is running."""
    code, _ = run_cmd(['systemctl', 'is-active', '--quiet', BRIDGE_SERVICE])
    return code == 0


def device_exists(path: str) -> bool:
    """Check if a serial device file exists."""
    return os.path.exists(path)


def topic_is_publishing() -> bool:
    """Check if /stepper_state topic has recent messages.

    Uses ros2 topic hz with a short timeout to verify the bridge is
    actively publishing state.
    """
    code, output = run_cmd(
        ['bash', '-c',
         'source /opt/ros/jazzy/setup.bash && '
         'timeout 5 ros2 topic echo --once /stepper_state 2>/dev/null'],
        timeout=8.0
    )
    return code == 0 and 'data' in output


def restart_bridge() -> bool:
    """Restart the bridge systemd service.

    Returns:
        True if restart command succeeded.
    """
    logger.warning('Restarting bridge service...')
    code, output = run_cmd(['sudo', 'systemctl', 'restart', BRIDGE_SERVICE])
    if code == 0:
        logger.info('Bridge service restarted successfully')
        time.sleep(8)  # Wait for bridge to connect
        return True
    else:
        logger.error('Failed to restart bridge: %s', output)
        return False


def main() -> None:
    """Main watchdog loop."""
    logger.info('Armold Watchdog started')
    logger.info('Monitoring: %s', BRIDGE_SERVICE)
    logger.info('Devices: %s', EINSY_DEVICE)
    logger.info('Check interval: %ds', CHECK_INTERVAL)

    restart_count = 0
    last_restart_time = 0

    # Wait for initial startup
    time.sleep(15)

    while True:
        try:
            needs_restart = False
            reason = ''

            # Check 1: Device exists
            if not device_exists(EINSY_DEVICE):
                needs_restart = True
                reason = f'Device missing: {EINSY_DEVICE}'

            # Check 2: Service is running
            elif not is_service_active():
                needs_restart = True
                reason = 'Bridge service not active'

            # Check 3: Topic is publishing (bridge is functional)
            elif not topic_is_publishing():
                needs_restart = True
                reason = '/stepper_state not publishing'

            if needs_restart:
                logger.warning('Issue detected: %s', reason)

                # Rate limit restarts
                now = time.time()
                if restart_count >= MAX_RESTARTS:
                    if now - last_restart_time < BACKOFF_TIME:
                        logger.error(
                            'Max restarts (%d) reached, backing off %ds',
                            MAX_RESTARTS, BACKOFF_TIME
                        )
                        time.sleep(BACKOFF_TIME)
                        restart_count = 0
                        continue

                # Only restart if device exists (no point restarting without USB)
                if device_exists(EINSY_DEVICE):
                    restart_bridge()
                    restart_count += 1
                    last_restart_time = now
                else:
                    logger.info('Waiting for device to reconnect...')
            else:
                # Reset counter on successful check
                if restart_count > 0:
                    logger.info('Bridge healthy, resetting restart counter')
                restart_count = 0

        except Exception as e:
            logger.error('Watchdog error: %s', e)

        time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    main()
