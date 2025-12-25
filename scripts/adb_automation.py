#!/usr/bin/env python3
"""
ADB Automation - Complex workflow automation for Android devices.
Provides high-level automation tasks and scripted workflows.
"""

import time
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime

from adb_controller import ADBController, ADBError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class AutomationStep:
    """Single automation step."""
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    delay_after: float = 0.5
    description: str = ""


@dataclass
class AutomationResult:
    """Result of automation run."""
    success: bool
    steps_completed: int
    total_steps: int
    duration: float
    errors: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)


class ADBAutomation:
    """High-level automation controller."""

    def __init__(self, device_serial: Optional[str] = None):
        """Initialize automation controller."""
        self.adb = ADBController(device_serial)
        self.screen_width, self.screen_height = self.adb.get_screen_size()

    def _execute_step(self, step: AutomationStep) -> bool:
        """Execute single automation step."""
        try:
            action = step.action.lower()
            params = step.params

            if action == 'tap':
                x = params.get('x', self.screen_width // 2)
                y = params.get('y', self.screen_height // 2)
                self.adb.tap(x, y)

            elif action == 'tap_center':
                self.adb.tap(self.screen_width // 2, self.screen_height // 2)

            elif action == 'tap_percent':
                x = int(self.screen_width * params.get('x_pct', 0.5))
                y = int(self.screen_height * params.get('y_pct', 0.5))
                self.adb.tap(x, y)

            elif action == 'swipe':
                self.adb.swipe(
                    params.get('x1', 0), params.get('y1', 0),
                    params.get('x2', 0), params.get('y2', 0),
                    params.get('duration', 300)
                )

            elif action == 'swipe_up':
                self.adb.scroll_down(params.get('steps', 1))

            elif action == 'swipe_down':
                self.adb.scroll_up(params.get('steps', 1))

            elif action == 'swipe_left':
                mid_y = self.screen_height // 2
                self.adb.swipe(
                    int(self.screen_width * 0.8), mid_y,
                    int(self.screen_width * 0.2), mid_y, 200
                )

            elif action == 'swipe_right':
                mid_y = self.screen_height // 2
                self.adb.swipe(
                    int(self.screen_width * 0.2), mid_y,
                    int(self.screen_width * 0.8), mid_y, 200
                )

            elif action == 'long_press':
                self.adb.long_press(
                    params.get('x', self.screen_width // 2),
                    params.get('y', self.screen_height // 2),
                    params.get('duration', 1000)
                )

            elif action == 'text':
                self.adb.input_text(params.get('text', ''))

            elif action == 'key':
                self.adb.key_event(params.get('keycode', 0))

            elif action == 'home':
                self.adb.press_home()

            elif action == 'back':
                self.adb.press_back()

            elif action == 'menu':
                self.adb.press_menu()

            elif action == 'enter':
                self.adb.press_enter()

            elif action == 'power':
                self.adb.press_power()

            elif action == 'wake':
                self.adb.wake_up()

            elif action == 'screenshot':
                path = params.get('path', f'screenshot_{int(time.time())}.png')
                self.adb.screenshot(path)
                return path

            elif action == 'start_app':
                self.adb.start_app(params.get('package', ''))

            elif action == 'stop_app':
                self.adb.force_stop(params.get('package', ''))

            elif action == 'wait':
                time.sleep(params.get('seconds', 1))

            elif action == 'shell':
                self.adb._shell(params.get('command', ''))

            else:
                logger.warning(f"Unknown action: {action}")
                return False

            time.sleep(step.delay_after)
            return True

        except Exception as e:
            logger.error(f"Step failed: {e}")
            return False

    def run_workflow(self, steps: List[AutomationStep],
                     stop_on_error: bool = True) -> AutomationResult:
        """
        Run automation workflow.

        Args:
            steps: List of automation steps
            stop_on_error: Stop if step fails

        Returns:
            AutomationResult with execution details
        """
        start_time = time.time()
        completed = 0
        errors = []
        screenshots = []

        for i, step in enumerate(steps):
            logger.info(f"Step {i + 1}/{len(steps)}: {step.action} - {step.description}")

            result = self._execute_step(step)

            if isinstance(result, str):
                screenshots.append(result)
                completed += 1
            elif result:
                completed += 1
            else:
                errors.append(f"Step {i + 1} failed: {step.action}")
                if stop_on_error:
                    break

        duration = time.time() - start_time

        return AutomationResult(
            success=len(errors) == 0,
            steps_completed=completed,
            total_steps=len(steps),
            duration=duration,
            errors=errors,
            screenshots=screenshots
        )

    def run_from_json(self, json_path: str) -> AutomationResult:
        """Run workflow from JSON file."""
        with open(json_path) as f:
            data = json.load(f)

        steps = []
        for step_data in data.get('steps', []):
            steps.append(AutomationStep(
                action=step_data['action'],
                params=step_data.get('params', {}),
                delay_after=step_data.get('delay', 0.5),
                description=step_data.get('description', '')
            ))

        return self.run_workflow(steps)


class AppTester(ADBAutomation):
    """Specialized automation for app testing."""

    def install_and_launch(self, apk_path: str, package: str,
                           take_screenshots: bool = True) -> Dict:
        """Install APK and launch app."""
        results = {
            'install': False,
            'launch': False,
            'screenshots': []
        }

        logger.info("Installing APK...")
        results['install'] = self.adb.install_apk(apk_path, replace=True)

        if not results['install']:
            return results

        logger.info("Launching app...")
        self.adb.start_app(package)
        time.sleep(3)
        results['launch'] = True

        if take_screenshots:
            path = f'launch_{int(time.time())}.png'
            self.adb.screenshot(path)
            results['screenshots'].append(path)

        return results

    def test_basic_navigation(self, package: str,
                              num_actions: int = 10) -> AutomationResult:
        """Test basic app navigation with random-ish taps and swipes."""
        steps = [
            AutomationStep('start_app', {'package': package}, description='Launch app'),
            AutomationStep('wait', {'seconds': 3}, description='Wait for load'),
            AutomationStep('screenshot', {'path': 'nav_start.png'}, description='Initial state'),
        ]

        for i in range(num_actions):
            if i % 3 == 0:
                steps.append(AutomationStep('tap_center', description=f'Tap {i + 1}'))
            elif i % 3 == 1:
                steps.append(AutomationStep('swipe_up', description=f'Scroll {i + 1}'))
            else:
                steps.append(AutomationStep('back', description=f'Back {i + 1}'))

        steps.append(AutomationStep('screenshot', {'path': 'nav_end.png'}, description='Final state'))

        return self.run_workflow(steps)

    def stress_test(self, package: str, duration_seconds: int = 60) -> Dict:
        """Run monkey stress test."""
        logger.info(f"Starting stress test for {duration_seconds}s...")

        events_per_second = 10
        total_events = duration_seconds * events_per_second

        self.adb._shell(
            f'monkey -p {package} --throttle 100 -v {total_events}'
        )

        return {
            'duration': duration_seconds,
            'events': total_events,
            'package': package
        }


class DeviceManager(ADBAutomation):
    """Device management automation."""

    def health_check(self) -> Dict:
        """Comprehensive device health check."""
        info = self.adb.get_device_info()

        return {
            'timestamp': datetime.now().isoformat(),
            'device': {
                'model': info.model,
                'android': info.android_version,
                'sdk': info.sdk_version,
            },
            'screen': {
                'width': info.screen_size[0],
                'height': info.screen_size[1],
            },
            'battery': {
                'level': info.battery_level,
            },
            'storage': self._get_storage_info(),
            'memory': self._get_memory_info(),
        }

    def _get_storage_info(self) -> Dict:
        """Get storage information."""
        output = self.adb._shell('df -h /data | tail -1')
        parts = output.split()
        if len(parts) >= 4:
            return {
                'total': parts[1],
                'used': parts[2],
                'available': parts[3],
                'use_percent': parts[4] if len(parts) > 4 else 'N/A'
            }
        return {}

    def _get_memory_info(self) -> Dict:
        """Get memory information."""
        output = self.adb._shell('cat /proc/meminfo | head -3')
        memory = {}
        for line in output.split('\n'):
            if ':' in line:
                key, value = line.split(':')
                memory[key.strip()] = value.strip()
        return memory

    def cleanup_device(self, clear_cache: bool = True,
                       clear_downloads: bool = False) -> Dict:
        """Clean up device storage."""
        results = {'cleared': []}

        if clear_cache:
            logger.info("Clearing cache...")
            self.adb._shell('rm -rf /data/local/tmp/*')
            results['cleared'].append('local_tmp')

        if clear_downloads:
            logger.info("Clearing downloads...")
            self.adb._shell('rm -rf /sdcard/Download/*')
            results['cleared'].append('downloads')

        return results

    def batch_uninstall(self, packages: List[str],
                        keep_data: bool = False) -> Dict:
        """Uninstall multiple apps."""
        results = {}
        for pkg in packages:
            logger.info(f"Uninstalling {pkg}...")
            results[pkg] = self.adb.uninstall(pkg, keep_data=keep_data)
        return results

    def extract_all_apks(self, output_dir: str = './apks') -> List[str]:
        """Extract all third-party APKs."""
        Path(output_dir).mkdir(exist_ok=True)
        extracted = []

        packages = self.adb.list_packages(third_party_only=True)

        for pkg in packages:
            try:
                apk_path = self.adb._shell(f'pm path {pkg}').split(':')[-1].strip()
                local_path = f'{output_dir}/{pkg}.apk'
                if self.adb.pull(apk_path, local_path):
                    extracted.append(local_path)
                    logger.info(f"Extracted: {pkg}")
            except Exception as e:
                logger.error(f"Failed to extract {pkg}: {e}")

        return extracted


class ScreenRecorder:
    """Screen recording manager."""

    def __init__(self, adb: ADBController):
        self.adb = adb
        self.recording = False

    def start(self, filename: str = 'recording.mp4',
              time_limit: int = 180, bit_rate: int = 4000000) -> None:
        """Start recording."""
        if self.recording:
            logger.warning("Already recording")
            return

        remote_path = f'/sdcard/{filename}'
        self.adb.screen_record(remote_path, time_limit, bit_rate)
        self.recording = True
        logger.info(f"Recording started: {remote_path}")

    def stop_and_pull(self, local_path: str = './recording.mp4',
                      remote_filename: str = 'recording.mp4') -> bool:
        """Stop recording and pull file."""
        remote_path = f'/sdcard/{remote_filename}'
        time.sleep(1)

        if self.adb.pull(remote_path, local_path):
            self.adb.rm(remote_path)
            self.recording = False
            logger.info(f"Recording saved: {local_path}")
            return True
        return False


def main():
    """Demo automation workflows."""
    print("=== ADB Automation Demo ===\n")

    auto = ADBAutomation()

    print("Device Health Check:")
    mgr = DeviceManager()
    health = mgr.health_check()
    print(json.dumps(health, indent=2))

    print("\n=== Demo Complete ===")


if __name__ == '__main__':
    main()
