# -*- coding: utf-8 -*-

import logging
import time
from typing import Dict, Any, Optional
from urllib.parse import urlencode, quote

_logger = logging.getLogger(__name__)


class JenkinsClient:
    """Service for Jenkins CI/CD integration"""
    
    def __init__(self, config):
        """
        Initialize Jenkins Client
        
        Args:
            config: qa.test.ai.config record
        """
        self.config = config
        self.url = config.jenkins_url.rstrip('/') if config.jenkins_url else ''
        self.user = config.jenkins_user
        self.token = config.jenkins_token
        self.job_name = config.jenkins_job_name
        self._crumb = None
        self._crumb_field = None
    
    def _get_crumb(self):
        """Get Jenkins CSRF crumb for POST requests"""
        import requests
        from requests.auth import HTTPBasicAuth
        
        if self._crumb:
            return self._crumb, self._crumb_field
        
        try:
            # Try new crumb issuer first
            response = requests.get(
                f"{self.url}/crumbIssuer/api/json",
                auth=HTTPBasicAuth(self.user, self.token),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self._crumb = data.get('crumb')
                self._crumb_field = data.get('crumbRequestField', 'Jenkins-Crumb')
                _logger.info(f"Got Jenkins crumb: {self._crumb_field}")
                return self._crumb, self._crumb_field
            elif response.status_code == 404:
                # CSRF protection might be disabled
                _logger.info("Jenkins CSRF protection appears to be disabled")
                return None, None
            else:
                _logger.warning(f"Failed to get crumb: {response.status_code}")
                return None, None
                
        except Exception as e:
            _logger.warning(f"Could not get Jenkins crumb: {str(e)}")
            return None, None
    
    def _make_post_request(self, url: str, data: Dict = None, params: Dict = None):
        """Make POST request with crumb if needed"""
        import requests
        from requests.auth import HTTPBasicAuth
        
        headers = {}
        
        # Get crumb for CSRF protection
        crumb, crumb_field = self._get_crumb()
        if crumb and crumb_field:
            headers[crumb_field] = crumb
        
        _logger.info(f"POST {url}")
        _logger.info(f"Headers: {headers}")
        _logger.info(f"Params: {params}")
        _logger.info(f"Data: {data}")
        
        response = requests.post(
            url,
            auth=HTTPBasicAuth(self.user, self.token),
            headers=headers,
            data=data,
            params=params,
            timeout=30,
            allow_redirects=False  # Important for getting Location header
        )
        
        _logger.info(f"Response: {response.status_code}")
        _logger.info(f"Response headers: {dict(response.headers)}")
        
        return response
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Jenkins server"""
        import requests
        from requests.auth import HTTPBasicAuth
        
        result = {
            'success': False,
            'message': '',
            'version': '',
        }
        
        try:
            response = requests.get(
                f"{self.url}/api/json",
                auth=HTTPBasicAuth(self.user, self.token),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                result['success'] = True
                result['message'] = 'Connected successfully'
                result['version'] = data.get('description', 'Jenkins')
                
                # Check if job exists
                jobs = [j['name'] for j in data.get('jobs', [])]
                if self.job_name and self.job_name not in jobs:
                    result['message'] += f"\nWarning: Job '{self.job_name}' not found in root. "
                    result['message'] += f"Available jobs: {', '.join(jobs[:5])}"
            elif response.status_code == 401:
                result['message'] = 'Authentication failed. Check username and API token.'
            elif response.status_code == 403:
                result['message'] = 'Access forbidden. Check user permissions.'
            else:
                result['message'] = f'Unexpected response: {response.status_code}'
                
            return result
            
        except requests.exceptions.ConnectionError:
            result['message'] = f'Cannot connect to {self.url}. Check URL and network.'
            return result
        except Exception as e:
            result['message'] = f'Connection error: {str(e)}'
            return result
    
    def trigger_build(self, job_name: str = None, parameters: Dict = None) -> int:
        """
        Trigger a Jenkins build
        
        Args:
            job_name: Jenkins job name (default from config)
            parameters: Build parameters
        
        Returns:
            Build number
        """
        import requests
        
        job_name = job_name or self.job_name
        
        # URL encode job name (handles spaces and special chars)
        encoded_job_name = quote(job_name, safe='')
        
        # Determine endpoint based on whether we have parameters
        if parameters:
            url = f"{self.url}/job/{encoded_job_name}/buildWithParameters"
        else:
            url = f"{self.url}/job/{encoded_job_name}/build"
        
        _logger.info(f"Triggering Jenkins build: {url}")
        _logger.info(f"Parameters: {parameters}")
        
        try:
            response = self._make_post_request(url, data=parameters)
            
            # Jenkins returns 201 for successful queue, or 302 redirect
            if response.status_code in (200, 201, 302):
                # Get build number from queue
                queue_url = response.headers.get('Location', '')
                _logger.info(f"Queue URL: {queue_url}")
                
                if queue_url:
                    build_number = self._get_build_number_from_queue(queue_url)
                else:
                    # Fallback: get last build number + 1
                    build_number = self._get_last_build_number(job_name) + 1
                
                _logger.info(f"Triggered Jenkins build #{build_number} for job {job_name}")
                return build_number
            
            # Handle specific errors
            elif response.status_code == 400:
                raise Exception(f"Bad request - check if job '{job_name}' is configured to accept parameters")
            elif response.status_code == 404:
                raise Exception(f"Job '{job_name}' not found at {self.url}")
            elif response.status_code == 403:
                raise Exception("Access forbidden - check user permissions for this job")
            elif response.status_code == 500:
                # Try to get more info from response
                error_detail = response.text[:500] if response.text else "No details"
                raise Exception(f"Jenkins server error (500). This usually means:\n"
                              f"1. Job is not parameterized but parameters were sent\n"
                              f"2. Required parameters are missing\n"
                              f"3. Jenkins plugin issue\n\n"
                              f"Details: {error_detail}")
            else:
                raise Exception(f"Failed to trigger build: HTTP {response.status_code}\n{response.text[:200]}")
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"Request failed: {str(e)}")
            raise Exception(f"Failed to connect to Jenkins: {str(e)}")
    
    def _get_build_number_from_queue(self, queue_url: str) -> int:
        """Get build number from queue item"""
        import requests
        from requests.auth import HTTPBasicAuth
        
        # Normalize queue URL
        if not queue_url.endswith('/'):
            queue_url += '/'
        
        api_url = f"{queue_url}api/json"
        _logger.info(f"Checking queue: {api_url}")
        
        # Wait for queue item to be processed
        for i in range(30):  # Wait up to 30 seconds
            try:
                response = requests.get(
                    api_url,
                    auth=HTTPBasicAuth(self.user, self.token),
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if build has started
                    if 'executable' in data and data['executable']:
                        build_number = data['executable'].get('number')
                        if build_number:
                            return build_number
                    
                    # Check if cancelled
                    if data.get('cancelled'):
                        raise Exception("Build was cancelled in queue")
                    
                    # Still waiting
                    why = data.get('why', 'Waiting...')
                    _logger.info(f"Queue status ({i+1}/30): {why}")
                
            except requests.exceptions.RequestException as e:
                _logger.warning(f"Queue check failed: {e}")
            
            time.sleep(1)
        
        # Fallback if queue times out
        _logger.warning("Timeout waiting for queue, using fallback")
        return self._get_last_build_number(self.job_name) + 1
    
    def _get_last_build_number(self, job_name: str) -> int:
        """Get the last build number for a job"""
        import requests
        from requests.auth import HTTPBasicAuth
        
        encoded_job_name = quote(job_name, safe='')
        
        try:
            response = requests.get(
                f"{self.url}/job/{encoded_job_name}/api/json",
                auth=HTTPBasicAuth(self.user, self.token),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                last_build = data.get('lastBuild') or {}
                return last_build.get('number', 0)
            
        except Exception as e:
            _logger.warning(f"Could not get last build number: {e}")
        
        return 0
    
    def get_build_status(self, job_name: str = None, build_number: int = None) -> Dict:
        """Get build status"""
        import requests
        from requests.auth import HTTPBasicAuth
        
        job_name = job_name or self.job_name
        encoded_job_name = quote(job_name, safe='')
        
        if build_number:
            url = f"{self.url}/job/{encoded_job_name}/{build_number}/api/json"
        else:
            url = f"{self.url}/job/{encoded_job_name}/lastBuild/api/json"
        
        try:
            response = requests.get(
                url,
                auth=HTTPBasicAuth(self.user, self.token),
                timeout=10
            )
            data = response.json()
            
            return {
                'number': data.get('number'),
                'result': data.get('result'),
                'building': data.get('building', False),
                'duration': data.get('duration', 0),
                'url': data.get('url'),
                'timestamp': data.get('timestamp'),
            }
            
        except Exception as e:
            _logger.error(f"Failed to get build status: {str(e)}")
            raise
    
    def get_build_log(self, job_name: str = None, build_number: int = None) -> str:
        """Get build console output"""
        import requests
        from requests.auth import HTTPBasicAuth
        
        job_name = job_name or self.job_name
        encoded_job_name = quote(job_name, safe='')
        
        if build_number:
            url = f"{self.url}/job/{encoded_job_name}/{build_number}/consoleText"
        else:
            url = f"{self.url}/job/{encoded_job_name}/lastBuild/consoleText"
        
        try:
            response = requests.get(
                url,
                auth=HTTPBasicAuth(self.user, self.token),
                timeout=30
            )
            return response.text
            
        except Exception as e:
            _logger.error(f"Failed to get build log: {str(e)}")
            raise
    
    def wait_for_build(self, job_name: str = None, build_number: int = None, 
                       timeout: int = 300) -> Dict:
        """Wait for build to complete"""
        job_name = job_name or self.job_name
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_build_status(job_name, build_number)
            
            if not status.get('building'):
                return status
            
            time.sleep(5)
        
        raise Exception(f"Timeout waiting for build to complete")
    
    def get_test_report(self, job_name: str = None, build_number: int = None) -> Dict:
        """Get Robot Framework test report from Jenkins"""
        import requests
        from requests.auth import HTTPBasicAuth
        
        job_name = job_name or self.job_name
        encoded_job_name = quote(job_name, safe='')
        
        if build_number:
            url = f"{self.url}/job/{encoded_job_name}/{build_number}/robot/api/json"
        else:
            url = f"{self.url}/job/{encoded_job_name}/lastBuild/robot/api/json"
        
        try:
            response = requests.get(
                url,
                auth=HTTPBasicAuth(self.user, self.token),
                timeout=30
            )
            
            if response.status_code == 404:
                return None
            
            return response.json()
            
        except Exception as e:
            _logger.error(f"Failed to get test report: {str(e)}")
            return None
```

---

## Important: Make Sure Jenkins Job Has Parameters

The 500 error often happens when the job is **not configured to accept parameters**. 

In your Jenkins job configuration, make sure you have:
```
☑ This project is parameterized

Add Parameter → String Parameter:
  Name: TEST_CASES
  Default: (empty)
  
Add Parameter → String Parameter:
  Name: BASE_URL
  Default: (empty)
  
Add Parameter → String Parameter:
  Name: RUN_ID
  Default: (empty)