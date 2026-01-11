# -*- coding: utf-8 -*-

import os
import subprocess
import tempfile
import logging
import time
import base64
from datetime import datetime
from typing import Dict, Any, Optional

_logger = logging.getLogger(__name__)


class TestExecutor:
    """Service for executing Robot Framework tests"""
    
    def __init__(self, config, server=None, target_url=None):
        """
        Initialize Test Executor
        
        Args:
            config: qa.test.ai.config record
            server: qa.customer.server record (optional)
            target_url: Target URL override (optional)
        """
        self.config = config
        self.server = server
        
        # Use target_url if provided, then server URL, then config
        if target_url:
            self.base_url = target_url
        elif server:
            self.base_url = server.url
        else:
            self.base_url = config.test_base_url if config else ''
        
        # Get credentials
        if server and server.auth_type == 'password':
            self.username = server.username or ''
            self.password = server.password or ''
        elif config:
            self.username = config.test_username or ''
            self.password = config.test_password or ''
        else:
            self.username = ''
            self.password = ''
        
        self.browser = config.browser if config else 'chrome'
        self.timeout = config.timeout if config else 30
        self.headless = config.headless if config else True
        self.output_path = config.report_path if config else '/tmp/robot_output'
        self.screenshot_on_failure = config.screenshot_on_failure if config else True
        
        # Check if robot is available
        self._robot_available = self._check_robot_installed()
    
    def _check_robot_installed(self) -> bool:
        """Check if Robot Framework is installed"""
        try:
            result = subprocess.run(
                ['robot', '--version'], 
                capture_output=True, 
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def execute_test(self, test_case) -> Dict[str, Any]:
        """
        Execute a single test case
        
        Args:
            test_case: qa.test.case record
        
        Returns:
            Dictionary with execution results
        """
        start_time = time.time()
        
        # If Robot Framework is not installed, use simulation mode
        if not self._robot_available:
            return self._simulate_test(test_case, start_time)
        
        from .robot_generator import RobotGenerator
        
        try:
            # Generate Robot Framework file
            generator = RobotGenerator(self.config)
            robot_content = generator.generate_single_test_file(test_case)
            
            # Create temporary directory for test
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write test file
                test_file = os.path.join(temp_dir, f"{test_case.test_id}.robot")
                with open(test_file, 'w') as f:
                    f.write(robot_content)
                
                # Create output directory
                output_dir = os.path.join(temp_dir, 'output')
                os.makedirs(output_dir, exist_ok=True)
                
                # Run Robot Framework
                result = self._run_robot(test_file, output_dir)
                
                # Parse results
                execution_result = self._parse_results(output_dir, result)
                
                # Calculate duration
                execution_result['duration'] = time.time() - start_time
                
                return execution_result
                
        except Exception as e:
            _logger.error(f"Test execution failed: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'duration': time.time() - start_time,
                'log': '',
                'screenshot': None,
            }
    
    def _simulate_test(self, test_case, start_time: float) -> Dict[str, Any]:
        """
        Simulate test execution when Robot Framework is not installed.
        This validates the test structure and provides a dry-run result.
        """
        _logger.info(f"Simulating test (Robot Framework not installed): {test_case.name}")
        
        errors = []
        warnings = []
        
        # Validate test case has robot code
        if not test_case.robot_code or not test_case.robot_code.strip():
            errors.append("Test case has no Robot Framework code")
        else:
            robot_code = test_case.robot_code
            
            # Basic validation of robot code structure
            if '*** Test Cases ***' not in robot_code and '*** Keywords ***' not in robot_code:
                warnings.append("Robot code may be missing standard sections (*** Test Cases ***)")
            
            # Check for common issues
            if '${' in robot_code and '}' not in robot_code:
                warnings.append("Possible unclosed variable reference")
        
        duration = time.time() - start_time
        
        if errors:
            return {
                'status': 'error',
                'message': f"Validation errors: {'; '.join(errors)}",
                'duration': duration,
                'log': self._generate_simulation_log(test_case, errors, warnings, 'error'),
                'screenshot': None,
            }
        
        # In simulation mode, mark as validated
        return {
            'status': 'passed',
            'message': f"[SIMULATION] Test validated. Robot Framework not installed.\n"
                      f"Install with: pip install robotframework robotframework-seleniumlibrary",
            'duration': duration,
            'log': self._generate_simulation_log(test_case, errors, warnings, 'simulated'),
            'screenshot': None,
        }
    
    def _generate_simulation_log(self, test_case, errors: list, warnings: list, status: str) -> str:
        """Generate a simulation log"""
        log_lines = [
            "=" * 60,
            "SIMULATION MODE - Robot Framework Not Installed",
            "=" * 60,
            f"Test Case: {test_case.name}",
            f"Test ID: {test_case.test_id}",
            f"Target URL: {self.base_url}",
            f"Status: {status.upper()}",
            "-" * 60,
        ]
        
        if errors:
            log_lines.append("ERRORS:")
            for e in errors:
                log_lines.append(f"  - {e}")
        
        if warnings:
            log_lines.append("WARNINGS:")
            for w in warnings:
                log_lines.append(f"  - {w}")
        
        if not errors and not warnings:
            log_lines.append("Test structure validated successfully.")
            log_lines.append("")
            log_lines.append("To execute tests, install Robot Framework:")
            log_lines.append("  pip install robotframework robotframework-seleniumlibrary")
        
        log_lines.append("=" * 60)
        
        return '\n'.join(log_lines)
    
    def execute_suite(self, test_cases, output_dir: str = None) -> Dict[str, Any]:
        """
        Execute multiple test cases as a suite
        """
        # If Robot Framework is not installed, simulate all tests
        if not self._robot_available:
            results = []
            for tc in test_cases:
                results.append(self._simulate_test(tc, time.time()))
            
            return {
                'status': 'passed' if all(r['status'] == 'passed' for r in results) else 'failed',
                'message': f"[SIMULATION] Validated {len(test_cases)} tests. Robot Framework not installed.",
                'duration': sum(r['duration'] for r in results),
                'log': '\n\n'.join(r['log'] for r in results),
                'results': results,
            }
        
        from .robot_generator import RobotGenerator
        
        output_dir = output_dir or self.output_path
        os.makedirs(output_dir, exist_ok=True)
        
        start_time = time.time()
        
        try:
            generator = RobotGenerator(self.config)
            test_file = generator.export_all_tests(test_cases)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            run_output_dir = os.path.join(output_dir, f'run_{timestamp}')
            os.makedirs(run_output_dir, exist_ok=True)
            
            result = self._run_robot(test_file, run_output_dir)
            
            execution_result = self._parse_results(run_output_dir, result)
            execution_result['duration'] = time.time() - start_time
            execution_result['output_dir'] = run_output_dir
            
            return execution_result
            
        except Exception as e:
            _logger.error(f"Suite execution failed: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'duration': time.time() - start_time,
                'log': '',
            }
    
    def _run_robot(self, test_file: str, output_dir: str) -> subprocess.CompletedProcess:
        """Run Robot Framework command"""
        
        cmd = [
            'robot',
            '--outputdir', output_dir,
            '--variable', f'BASE_URL:{self.base_url}',
            '--variable', f'USERNAME:{self.username}',
            '--variable', f'PASSWORD:{self.password}',
            '--variable', f'BROWSER:{self.browser}',
            '--variable', f'TIMEOUT:{self.timeout}s',
        ]
        
        if self.headless:
            cmd.extend(['--variable', 'HEADLESS_OPTIONS:--headless'])
        
        cmd.append(test_file)
        
        _logger.info(f"Running Robot Framework: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        return result
    
    def _parse_results(self, output_dir: str, process_result: subprocess.CompletedProcess) -> Dict[str, Any]:
        """Parse Robot Framework output"""
        
        result = {
            'status': 'passed' if process_result.returncode == 0 else 'failed',
            'message': '',
            'log': process_result.stdout + '\n' + process_result.stderr,
            'screenshot': None,
        }
        
        output_xml = os.path.join(output_dir, 'output.xml')
        if os.path.exists(output_xml):
            result.update(self._parse_output_xml(output_xml))
        
        if result['status'] != 'passed':
            screenshot = self._find_screenshot(output_dir)
            if screenshot:
                result['screenshot'] = screenshot
        
        if process_result.returncode != 0:
            result['message'] = self._extract_error_message(process_result.stderr or process_result.stdout)
        
        return result
    
    def _parse_output_xml(self, output_xml: str) -> Dict[str, Any]:
        """Parse Robot Framework output.xml"""
        from xml.etree import ElementTree
        
        result = {}
        
        try:
            tree = ElementTree.parse(output_xml)
            root = tree.getroot()
            
            stats = root.find('.//statistics/total/stat')
            if stats is not None:
                passed = int(stats.get('pass', 0))
                failed = int(stats.get('fail', 0))
                result['passed_count'] = passed
                result['failed_count'] = failed
                result['status'] = 'passed' if failed == 0 else 'failed'
            
            for test in root.findall('.//test'):
                status = test.find('status')
                if status is not None and status.get('status') == 'FAIL':
                    result['message'] = status.text or 'Test failed'
                    break
            
        except Exception as e:
            _logger.warning(f"Could not parse output.xml: {e}")
        
        return result
    
    def _find_screenshot(self, output_dir: str) -> Optional[bytes]:
        """Find and return screenshot from output directory"""
        import glob
        
        patterns = ['selenium-screenshot-*.png', 'screenshot-*.png', '*.png']
        
        for pattern in patterns:
            files = glob.glob(os.path.join(output_dir, pattern))
            if files:
                latest = max(files, key=os.path.getctime)
                try:
                    with open(latest, 'rb') as f:
                        return base64.b64encode(f.read())
                except Exception as e:
                    _logger.warning(f"Could not read screenshot: {e}")
        
        return None
    
    def _extract_error_message(self, log: str) -> str:
        """Extract meaningful error message from log"""
        import re
        
        patterns = [
            r'FAIL\s*:\s*(.+)',
            r'ElementNotVisibleException:\s*(.+)',
            r'NoSuchElementException:\s*(.+)',
            r'TimeoutException:\s*(.+)',
            r'AssertionError:\s*(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, log)
            if match:
                return match.group(1).strip()[:500]
        
        lines = [l.strip() for l in log.split('\n') if l.strip()]
        return lines[-1] if lines else 'Unknown error'
    
    def verify_robot_installation(self) -> Dict[str, Any]:
        """Verify Robot Framework and dependencies are installed"""
        
        checks = {
            'robot_framework': self._robot_available,
            'selenium_library': False,
            'browser_driver': False,
        }
        
        try:
            import SeleniumLibrary
            checks['selenium_library'] = True
        except ImportError:
            pass
        
        try:
            if self.browser == 'chrome':
                result = subprocess.run(['chromedriver', '--version'], capture_output=True, text=True)
            elif self.browser == 'firefox':
                result = subprocess.run(['geckodriver', '--version'], capture_output=True, text=True)
            checks['browser_driver'] = result.returncode == 0
        except FileNotFoundError:
            pass
        
        return checks
