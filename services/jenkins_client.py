# -*- coding: utf-8 -*-

import logging
import time
from typing import Dict, Any, Optional

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
    
    def test_connection(self) -> bool:
        """Test connection to Jenkins server"""
        import requests
        from requests.auth import HTTPBasicAuth
        
        try:
            response = requests.get(
                f"{self.url}/api/json",
                auth=HTTPBasicAuth(self.user, self.token),
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            _logger.error(f"Jenkins connection failed: {str(e)}")
            raise
    
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
        from requests.auth import HTTPBasicAuth
        
        job_name = job_name or self.job_name
        
        # Build URL
        if parameters:
            url = f"{self.url}/job/{job_name}/buildWithParameters"
        else:
            url = f"{self.url}/job/{job_name}/build"
        
        try:
            response = requests.post(
                url,
                auth=HTTPBasicAuth(self.user, self.token),
                data=parameters or {},
                timeout=30
            )
            
            if response.status_code not in (200, 201):
                raise Exception(f"Failed to trigger build: {response.status_code}")
            
            # Get build number from queue
            queue_url = response.headers.get('Location', '')
            if queue_url:
                build_number = self._get_build_number_from_queue(queue_url)
            else:
                # Fallback: get last build number
                build_number = self._get_last_build_number(job_name) + 1
            
            _logger.info(f"Triggered Jenkins build #{build_number} for job {job_name}")
            return build_number
            
        except Exception as e:
            _logger.error(f"Failed to trigger Jenkins build: {str(e)}")
            raise
    
    def _get_build_number_from_queue(self, queue_url: str) -> int:
        """Get build number from queue item"""
        import requests
        from requests.auth import HTTPBasicAuth
        
        # Wait for queue item to be processed
        for _ in range(30):  # Wait up to 30 seconds
            try:
                response = requests.get(
                    f"{queue_url}api/json",
                    auth=HTTPBasicAuth(self.user, self.token),
                    timeout=10
                )
                data = response.json()
                
                if 'executable' in data:
                    return data['executable']['number']
                
            except Exception:
                pass
            
            time.sleep(1)
        
        raise Exception("Timeout waiting for build to start")
    
    def _get_last_build_number(self, job_name: str) -> int:
        """Get the last build number for a job"""
        import requests
        from requests.auth import HTTPBasicAuth
        
        response = requests.get(
            f"{self.url}/job/{job_name}/api/json",
            auth=HTTPBasicAuth(self.user, self.token),
            timeout=10
        )
        data = response.json()
        
        last_build = data.get('lastBuild', {})
        return last_build.get('number', 0)
    
    def get_build_status(self, job_name: str = None, build_number: int = None) -> Dict:
        """
        Get build status
        
        Args:
            job_name: Jenkins job name
            build_number: Build number (default: last build)
        
        Returns:
            Build status dictionary
        """
        import requests
        from requests.auth import HTTPBasicAuth
        
        job_name = job_name or self.job_name
        
        if build_number:
            url = f"{self.url}/job/{job_name}/{build_number}/api/json"
        else:
            url = f"{self.url}/job/{job_name}/lastBuild/api/json"
        
        try:
            response = requests.get(
                url,
                auth=HTTPBasicAuth(self.user, self.token),
                timeout=10
            )
            data = response.json()
            
            return {
                'number': data.get('number'),
                'result': data.get('result'),  # SUCCESS, FAILURE, UNSTABLE, null (building)
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
        
        if build_number:
            url = f"{self.url}/job/{job_name}/{build_number}/consoleText"
        else:
            url = f"{self.url}/job/{job_name}/lastBuild/consoleText"
        
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
        """
        Wait for build to complete
        
        Args:
            job_name: Jenkins job name
            build_number: Build number
            timeout: Maximum wait time in seconds
        
        Returns:
            Final build status
        """
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
        
        if build_number:
            url = f"{self.url}/job/{job_name}/{build_number}/robot/api/json"
        else:
            url = f"{self.url}/job/{job_name}/lastBuild/robot/api/json"
        
        try:
            response = requests.get(
                url,
                auth=HTTPBasicAuth(self.user, self.token),
                timeout=30
            )
            
            if response.status_code == 404:
                return None  # No robot report
            
            return response.json()
            
        except Exception as e:
            _logger.error(f"Failed to get test report: {str(e)}")
            return None
    
    def create_job(self, job_name: str, config_xml: str) -> bool:
        """Create a new Jenkins job"""
        import requests
        from requests.auth import HTTPBasicAuth
        
        url = f"{self.url}/createItem"
        
        try:
            response = requests.post(
                url,
                auth=HTTPBasicAuth(self.user, self.token),
                headers={'Content-Type': 'application/xml'},
                data=config_xml,
                params={'name': job_name},
                timeout=30
            )
            
            return response.status_code == 200
            
        except Exception as e:
            _logger.error(f"Failed to create Jenkins job: {str(e)}")
            raise
    
    def get_default_job_config(self) -> str:
        """Get default Jenkins job configuration for Robot Framework"""
        return """<?xml version='1.1' encoding='UTF-8'?>
<project>
  <description>Odoo Robot Framework Tests - Generated by QA Test Generator</description>
  <keepDependencies>false</keepDependencies>
  <properties>
    <hudson.model.ParametersDefinitionProperty>
      <parameterDefinitions>
        <hudson.model.StringParameterDefinition>
          <name>TEST_CASES</name>
          <description>Comma-separated test case IDs</description>
          <defaultValue></defaultValue>
          <trim>true</trim>
        </hudson.model.StringParameterDefinition>
        <hudson.model.StringParameterDefinition>
          <name>BASE_URL</name>
          <description>Odoo base URL</description>
          <defaultValue>http://localhost:8069</defaultValue>
          <trim>true</trim>
        </hudson.model.StringParameterDefinition>
        <hudson.model.StringParameterDefinition>
          <name>RUN_ID</name>
          <description>QA Test Generator Run ID</description>
          <defaultValue></defaultValue>
          <trim>true</trim>
        </hudson.model.StringParameterDefinition>
      </parameterDefinitions>
    </hudson.model.ParametersDefinitionProperty>
  </properties>
  <scm class="hudson.scm.NullSCM"/>
  <builders>
    <hudson.tasks.Shell>
      <command>
#!/bin/bash
cd $WORKSPACE

# Install dependencies
pip install robotframework robotframework-seleniumlibrary

# Run tests
robot --variable BASE_URL:$BASE_URL \\
      --outputdir results/ \\
      --xunit xunit.xml \\
      tests/
      
# Report status back to Odoo
curl -X POST "$ODOO_CALLBACK_URL" \\
     -H "Content-Type: application/json" \\
     -d '{"run_id": "'$RUN_ID'", "status": "'$BUILD_STATUS'"}'
      </command>
    </hudson.tasks.Shell>
  </builders>
  <publishers>
    <hudson.plugins.robot.RobotPublisher plugin="robot@3.2.0">
      <outputPath>results</outputPath>
      <reportFileName>report.html</reportFileName>
      <logFileName>log.html</logFileName>
      <outputFileName>output.xml</outputFileName>
      <passThreshold>100.0</passThreshold>
      <unstableThreshold>75.0</unstableThreshold>
    </hudson.plugins.robot.RobotPublisher>
  </publishers>
</project>"""
