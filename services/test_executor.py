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
    
    def __init__(self, config):
        """
        Initialize Test Executor
        
        Args:
            config: qa.test.ai.config record
        """
        self.config = config
        self.base_url = config.test_base_url
        self.username = config.test_username
        self.password = config.test_password
        self.browser = config.browser
        self.timeout = config.timeout
        self.headless = config.headless
        self.output_path = config.report_path
        self.screenshot_on_failure = config.screenshot_on_failure
    
    def execute_test(self, test_case) -> Dict[str, Any]:
        """
        Execute a single test case
        
        Args:
            test_case: qa.test.case record
        
        Returns:
            Dictionary with execution results
        """
        from .robot_generator import RobotGenerator
        
        start_time = time.time()
        
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
    
    def execute_suite(self, test_cases, output_dir: str = None) -> Dict[str, Any]:
        """
        Execute multiple test cases as a suite
        
        Args:
            test_cases: List of qa.test.case records
            output_dir: Optional output directory
        
        Returns:
            Dictionary with execution results
        """
        from .robot_generator import RobotGenerator
        
        output_dir = output_dir or self.output_path
        os.makedirs(output_dir, exist_ok=True)
        
        start_time = time.time()
        
        try:
            # Generate combined Robot Framework file
            generator = RobotGenerator(self.config)
            test_file = generator.export_all_tests(test_cases)
            
            # Create timestamped output directory
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            run_output_dir = os.path.join(output_dir, f'run_{timestamp}')
            os.makedirs(run_output_dir, exist_ok=True)
            
            # Run Robot Framework
            result = self._run_robot(test_file, run_output_dir)
            
            # Parse results
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
        
        # Build command
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
        
        # Run command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
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
        
        # Try to parse output.xml for detailed results
        output_xml = os.path.join(output_dir, 'output.xml')
        if os.path.exists(output_xml):
            result.update(self._parse_output_xml(output_xml))
        
        # Check for failure screenshots
        if result['status'] != 'passed':
            screenshot = self._find_screenshot(output_dir)
            if screenshot:
                result['screenshot'] = screenshot
        
        # Get error message from log
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
            
            # Get statistics
            stats = root.find('.//statistics/total/stat')
            if stats is not None:
                passed = int(stats.get('pass', 0))
                failed = int(stats.get('fail', 0))
                result['passed_count'] = passed
                result['failed_count'] = failed
                result['status'] = 'passed' if failed == 0 else 'failed'
            
            # Get error messages from failed tests
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
        
        # Look for common screenshot filenames
        patterns = [
            'selenium-screenshot-*.png',
            'screenshot-*.png',
            '*_screenshot.png',
            '*.png',
        ]
        
        import glob
        
        for pattern in patterns:
            files = glob.glob(os.path.join(output_dir, pattern))
            if files:
                # Get most recent file
                latest = max(files, key=os.path.getctime)
                try:
                    with open(latest, 'rb') as f:
                        return base64.b64encode(f.read())
                except Exception as e:
                    _logger.warning(f"Could not read screenshot: {e}")
        
        return None
    
    def _extract_error_message(self, log: str) -> str:
        """Extract meaningful error message from log"""
        
        # Common Robot Framework error patterns
        patterns = [
            r'FAIL\s*:\s*(.+)',
            r'ElementNotVisibleException:\s*(.+)',
            r'NoSuchElementException:\s*(.+)',
            r'TimeoutException:\s*(.+)',
            r'AssertionError:\s*(.+)',
        ]
        
        import re
        
        for pattern in patterns:
            match = re.search(pattern, log)
            if match:
                return match.group(1).strip()[:500]  # Limit length
        
        # Return last line if no pattern matched
        lines = [l.strip() for l in log.split('\n') if l.strip()]
        return lines[-1] if lines else 'Unknown error'
    
    def verify_robot_installation(self) -> Dict[str, Any]:
        """Verify Robot Framework and dependencies are installed"""
        
        checks = {
            'robot_framework': False,
            'selenium_library': False,
            'browser_driver': False,
        }
        
        # Check Robot Framework
        try:
            result = subprocess.run(['robot', '--version'], capture_output=True, text=True)
            checks['robot_framework'] = result.returncode == 0
        except FileNotFoundError:
            pass
        
        # Check SeleniumLibrary
        try:
            import SeleniumLibrary
            checks['selenium_library'] = True
        except ImportError:
            pass
        
        # Check browser driver
        try:
            if self.browser == 'chrome':
                result = subprocess.run(['chromedriver', '--version'], capture_output=True, text=True)
            elif self.browser == 'firefox':
                result = subprocess.run(['geckodriver', '--version'], capture_output=True, text=True)
            checks['browser_driver'] = result.returncode == 0
        except FileNotFoundError:
            pass
        
        return checks
