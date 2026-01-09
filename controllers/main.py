# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request, Response
import json
import logging
import base64
import zipfile
import io
import tempfile
import os

_logger = logging.getLogger(__name__)


class QATestController(http.Controller):
    """Controller for QA Test Generator API endpoints"""

    # ==================== Authentication Helper ====================
    
    def _check_api_key(self):
        """Check API key from Authorization header"""
        auth_header = request.httprequest.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            api_key = auth_header[7:]
            config = request.env['qa.test.ai.config'].sudo().search([
                ('api_key', '=', api_key),
                ('active', '=', True)
            ], limit=1)
            return config.exists()
        return False

    # ==================== Health Check ====================
    
    @http.route('/api/v1/qa/health', type='http', auth='public', methods=['GET'], csrf=False)
    def api_health(self, **kwargs):
        """Health check endpoint"""
        return Response(
            json.dumps({'status': 'ok', 'service': 'qa-test-generator'}),
            content_type='application/json'
        )

    # ==================== Customer API ====================
    
    @http.route('/api/v1/qa/customers', type='http', auth='public', methods=['GET'], csrf=False)
    def api_get_customers(self, **kwargs):
        """
        Get list of customers with their test suites
        
        GET /api/v1/qa/customers
        Authorization: Bearer <api_key>
        """
        if not self._check_api_key():
            return Response(json.dumps({'error': 'Unauthorized'}), status=401, content_type='application/json')
        
        try:
            customers = request.env['qa.customer'].sudo().search([('active', '=', True)])
            
            result = []
            for customer in customers:
                # Get staging server
                staging_server = customer.server_ids.filtered(lambda s: s.environment == 'staging')[:1]
                
                result.append({
                    'id': customer.id,
                    'name': customer.name,
                    'code': customer.code,
                    'odoo_version': customer.odoo_version,
                    'staging_url': staging_server.url if staging_server else None,
                    'default_suite_id': customer.suite_ids[0].id if customer.suite_ids else None,
                    'suite_ids': customer.suite_ids.ids,
                    'server_ids': [{
                        'id': s.id,
                        'name': s.name,
                        'environment': s.environment,
                        'url': s.url,
                    } for s in customer.server_ids],
                })
            
            return Response(json.dumps(result), content_type='application/json')
            
        except Exception as e:
            _logger.error(f"API error: {str(e)}")
            return Response(json.dumps({'error': str(e)}), status=500, content_type='application/json')

    # ==================== Test Download API ====================
    
    @http.route('/api/v1/qa/download/<int:suite_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def api_download_tests(self, suite_id, **kwargs):
        """
        Download test files as ZIP for Jenkins
        
        GET /api/v1/qa/download/<suite_id>
        Authorization: Bearer <api_key>
        
        Returns: ZIP file containing Robot Framework tests
        """
        if not self._check_api_key():
            return Response(json.dumps({'error': 'Unauthorized'}), status=401, content_type='application/json')
        
        try:
            suite = request.env['qa.test.suite'].sudo().browse(suite_id)
            if not suite.exists():
                return Response(json.dumps({'error': 'Suite not found'}), status=404, content_type='application/json')
            
            # Create ZIP file in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                
                # Add each test case's robot code
                for test_case in suite.test_case_ids:
                    if test_case.robot_code:
                        filename = f"tests/{test_case.test_id or f'test_{test_case.id}'}.robot"
                        zip_file.writestr(filename, test_case.robot_code)
                
                # Add resource file with common keywords
                resource_content = self._generate_resource_file(suite)
                zip_file.writestr('tests/resources/common.resource', resource_content)
                
                # Add variables file
                variables_content = self._generate_variables_file(suite)
                zip_file.writestr('tests/resources/variables.py', variables_content)
                
                # Add requirements file
                requirements = """robotframework>=6.0
robotframework-seleniumlibrary>=6.0
robotframework-requests>=0.9
"""
                zip_file.writestr('requirements.txt', requirements)
            
            zip_buffer.seek(0)
            
            return Response(
                zip_buffer.getvalue(),
                headers={
                    'Content-Type': 'application/zip',
                    'Content-Disposition': f'attachment; filename=tests_{suite_id}.zip'
                }
            )
            
        except Exception as e:
            _logger.error(f"Download error: {str(e)}")
            return Response(json.dumps({'error': str(e)}), status=500, content_type='application/json')
    
    def _generate_resource_file(self, suite):
        """Generate common resource file"""
        return """*** Settings ***
Library    SeleniumLibrary
Library    Collections
Library    String
Library    DateTime

*** Keywords ***
Login To Odoo
    [Arguments]    ${username}    ${password}    ${url}=${SERVER_URL}
    Open Browser    ${url}/web/login    ${BROWSER}    options=${BROWSER_OPTIONS}
    Maximize Browser Window
    Input Text    login    ${username}
    Input Text    password    ${password}
    Click Button    xpath=//button[@type='submit']
    Wait Until Page Contains Element    xpath=//a[contains(@class, 'o_menu_toggle')]    timeout=30s

Logout From Odoo
    Click Element    xpath=//a[contains(@class, 'o_user_menu')]
    Click Link    xpath=//a[@data-menu='logout']

Navigate To
    [Arguments]    @{menu_path}
    FOR    ${menu}    IN    @{menu_path}
        Click Link    xpath=//a[contains(@class, 'o_menu_entry_lvl_') and contains(text(), '${menu}')]
        Sleep    0.5s
    END
    Wait Until Page Contains Element    xpath=//div[contains(@class, 'o_content')]    timeout=30s

Click Button With Text
    [Arguments]    ${text}
    Click Button    xpath=//button[contains(text(), '${text}') or contains(., '${text}')]

Fill Field
    [Arguments]    ${field_name}    ${value}
    Input Text    xpath=//input[@name='${field_name}'] | //textarea[@name='${field_name}']    ${value}

Select Dropdown Value
    [Arguments]    ${field_name}    ${value}
    Click Element    xpath=//div[@name='${field_name}']//input
    Wait Until Element Is Visible    xpath=//ul[contains(@class, 'ui-autocomplete')]
    Click Element    xpath=//li[contains(text(), '${value}')]

Verify Field Value
    [Arguments]    ${field_name}    ${expected_value}
    ${actual}=    Get Value    xpath=//input[@name='${field_name}']
    Should Be Equal    ${actual}    ${expected_value}

Take Screenshot On Failure
    [Teardown]    Run Keyword If Test Failed    Capture Page Screenshot
"""
    
    def _generate_variables_file(self, suite):
        """Generate variables file"""
        config = request.env['qa.test.ai.config'].sudo().search([], limit=1)
        base_url = config.test_base_url if config else 'http://localhost:8069'
        
        return f"""# -*- coding: utf-8 -*-
# Generated by QA Test Generator

SERVER_URL = '{base_url}'
BROWSER = 'chrome'
BROWSER_OPTIONS = 'add_argument("--headless"); add_argument("--no-sandbox"); add_argument("--disable-dev-shm-usage")'

# Test credentials (override via command line)
TEST_USER = 'admin'
TEST_PASSWORD = 'admin'

# Timeouts
IMPLICIT_WAIT = 10
PAGE_LOAD_TIMEOUT = 30
"""

    # ==================== Results Upload API ====================
    
    @http.route('/api/v1/qa/results', type='http', auth='public', methods=['POST'], csrf=False)
    def api_upload_results(self, **kwargs):
        """
        Upload test results from Jenkins
        
        POST /api/v1/qa/results
        Authorization: Bearer <api_key>
        Content-Type: multipart/form-data
        
        Parameters:
            run_id: Test run ID
            output_xml: Robot Framework output.xml file
            log_html: Robot Framework log.html file (optional)
            report_html: Robot Framework report.html file (optional)
        """
        if not self._check_api_key():
            return Response(json.dumps({'error': 'Unauthorized'}), status=401, content_type='application/json')
        
        try:
            run_id = int(request.params.get('run_id', 0))
            if not run_id:
                return Response(json.dumps({'error': 'run_id is required'}), status=400, content_type='application/json')
            
            run = request.env['qa.test.run'].sudo().browse(run_id)
            if not run.exists():
                return Response(json.dumps({'error': 'Run not found'}), status=404, content_type='application/json')
            
            # Get uploaded files
            output_xml = request.httprequest.files.get('output_xml')
            log_html = request.httprequest.files.get('log_html')
            report_html = request.httprequest.files.get('report_html')
            
            if not output_xml:
                return Response(json.dumps({'error': 'output_xml is required'}), status=400, content_type='application/json')
            
            # Save output.xml temporarily and parse
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp:
                tmp.write(output_xml.read())
                tmp_path = tmp.name
            
            try:
                # Parse Robot Framework results
                results = self._parse_robot_results(tmp_path)
                
                # Update run
                run.write({
                    'state': 'passed' if results['failed'] == 0 else 'failed',
                    'total_tests': results['total'],
                    'passed_tests': results['passed'],
                    'failed_tests': results['failed'],
                    'pass_rate': results['pass_rate'],
                    'end_time': results.get('end_time'),
                    'duration': results.get('duration', 0),
                })
                
                # Create individual test results
                for test_result in results.get('tests', []):
                    # Find matching test case
                    test_case = request.env['qa.test.case'].sudo().search([
                        ('name', 'ilike', test_result['name'])
                    ], limit=1)
                    
                    request.env['qa.test.result'].sudo().create({
                        'run_id': run.id,
                        'test_case_id': test_case.id if test_case else False,
                        'status': 'passed' if test_result['passed'] else 'failed',
                        'duration': test_result.get('duration', 0),
                        'message': test_result.get('message', ''),
                    })
                
                # Store attachments
                if log_html:
                    request.env['ir.attachment'].sudo().create({
                        'name': f'log_{run.id}.html',
                        'datas': base64.b64encode(log_html.read()),
                        'res_model': 'qa.test.run',
                        'res_id': run.id,
                    })
                
                if report_html:
                    request.env['ir.attachment'].sudo().create({
                        'name': f'report_{run.id}.html',
                        'datas': base64.b64encode(report_html.read()),
                        'res_model': 'qa.test.run',
                        'res_id': run.id,
                    })
                
            finally:
                os.unlink(tmp_path)
            
            return Response(json.dumps({
                'success': True,
                'run_id': run.id,
                'state': run.state,
                'pass_rate': run.pass_rate,
            }), content_type='application/json')
            
        except Exception as e:
            _logger.error(f"Upload error: {str(e)}")
            return Response(json.dumps({'error': str(e)}), status=500, content_type='application/json')
    
    def _parse_robot_results(self, xml_path):
        """Parse Robot Framework output.xml"""
        try:
            from robot.api import ExecutionResult
            
            result = ExecutionResult(xml_path)
            stats = result.statistics.total
            
            tests = []
            for test in result.suite.all_tests:
                tests.append({
                    'name': test.name,
                    'passed': test.passed,
                    'duration': test.elapsedtime / 1000,  # Convert to seconds
                    'message': test.message if not test.passed else '',
                    'tags': list(test.tags),
                })
            
            return {
                'total': stats.total,
                'passed': stats.passed,
                'failed': stats.failed,
                'pass_rate': (stats.passed / stats.total * 100) if stats.total > 0 else 0,
                'duration': result.suite.elapsedtime / 1000,
                'tests': tests,
            }
            
        except ImportError:
            # Fallback: parse XML manually
            import xml.etree.ElementTree as ET
            
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            total = int(root.find('.//stat[@name="All Tests"]').text or 0)
            passed = int(root.find('.//stat[@name="All Tests"]').get('pass', 0))
            failed = int(root.find('.//stat[@name="All Tests"]').get('fail', 0))
            
            return {
                'total': total,
                'passed': passed,
                'failed': failed,
                'pass_rate': (passed / total * 100) if total > 0 else 0,
                'tests': [],
            }

    # ==================== Trigger API ====================
    
    @http.route('/api/v1/qa/trigger/<int:suite_id>', type='http', auth='public', methods=['POST'], csrf=False)
    def api_trigger_tests(self, suite_id, **kwargs):
        """
        Trigger test execution for a suite
        
        POST /api/v1/qa/trigger/<suite_id>
        Authorization: Bearer <api_key>
        Content-Type: application/json
        
        Body:
        {
            "server_id": 1,  // Optional: specific server to test
            "tags": ["smoke"],  // Optional: filter by tags
            "jenkins": true  // Optional: use Jenkins (default: true)
        }
        """
        if not self._check_api_key():
            return Response(json.dumps({'error': 'Unauthorized'}), status=401, content_type='application/json')
        
        try:
            suite = request.env['qa.test.suite'].sudo().browse(suite_id)
            if not suite.exists():
                return Response(json.dumps({'error': 'Suite not found'}), status=404, content_type='application/json')
            
            # Parse JSON body
            try:
                body = json.loads(request.httprequest.data.decode('utf-8'))
            except:
                body = {}
            
            server_id = body.get('server_id')
            use_jenkins = body.get('jenkins', True)
            
            # Create test run
            run = request.env['qa.test.run'].sudo().create({
                'name': f"API Run - {suite.name}",
                'suite_id': suite.id,
                'test_case_ids': [(6, 0, suite.test_case_ids.ids)],
                'server_id': server_id,
                'triggered_by': 'api',
            })
            
            # Trigger Jenkins if configured
            if use_jenkins:
                config = request.env['qa.test.ai.config'].sudo().search([
                    ('jenkins_enabled', '=', True)
                ], limit=1)
                
                if config:
                    from ..services.jenkins_client import JenkinsClient
                    jenkins = JenkinsClient(config)
                    
                    # Get server URL
                    server_url = config.test_base_url
                    if server_id:
                        server = request.env['qa.customer.server'].sudo().browse(server_id)
                        server_url = server.url if server.exists() else server_url
                    
                    build_number = jenkins.trigger_build(parameters={
                        'SUITE_ID': str(suite_id),
                        'RUN_ID': str(run.id),
                        'SERVER_URL': server_url,
                        'CALLBACK_URL': request.httprequest.host_url.rstrip('/'),
                    })
                    
                    run.write({
                        'jenkins_build_number': build_number,
                        'state': 'running',
                    })
            
            return Response(json.dumps({
                'success': True,
                'run_id': run.id,
                'suite_id': suite.id,
                'state': run.state,
                'jenkins_build': run.jenkins_build_number if use_jenkins else None,
            }), content_type='application/json')
            
        except Exception as e:
            _logger.error(f"Trigger error: {str(e)}")
            return Response(json.dumps({'error': str(e)}), status=500, content_type='application/json')

    # ==================== Status API ====================
    
    @http.route('/api/v1/qa/status/<int:run_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def api_get_status(self, run_id, **kwargs):
        """
        Get status of a test run
        
        GET /api/v1/qa/status/<run_id>
        Authorization: Bearer <api_key>
        """
        if not self._check_api_key():
            return Response(json.dumps({'error': 'Unauthorized'}), status=401, content_type='application/json')
        
        try:
            run = request.env['qa.test.run'].sudo().browse(run_id)
            if not run.exists():
                return Response(json.dumps({'error': 'Run not found'}), status=404, content_type='application/json')
            
            return Response(json.dumps({
                'run_id': run.id,
                'name': run.name,
                'state': run.state,
                'total_tests': run.total_tests,
                'passed_tests': run.passed_tests,
                'failed_tests': run.failed_tests,
                'pass_rate': run.pass_rate,
                'duration': run.duration,
                'start_time': run.start_time.isoformat() if run.start_time else None,
                'end_time': run.end_time.isoformat() if run.end_time else None,
                'jenkins_build': run.jenkins_build_number,
            }), content_type='application/json')
            
        except Exception as e:
            _logger.error(f"Status error: {str(e)}")
            return Response(json.dumps({'error': str(e)}), status=500, content_type='application/json')

    # ==================== Legacy Endpoints (for backward compatibility) ====================

    @http.route('/qa_test/api/run', type='json', auth='user', methods=['POST'])
    def api_create_run(self, **kwargs):
        """Legacy: API endpoint to create and execute a test run"""
        try:
            suite_id = kwargs.get('suite_id')
            test_case_ids = kwargs.get('test_case_ids', [])
            environment = kwargs.get('environment', 'local')
            auto_execute = kwargs.get('auto_execute', False)
            
            # Get test cases
            if suite_id:
                suite = request.env['qa.test.suite'].browse(suite_id)
                test_case_ids = suite.test_case_ids.ids
            
            if not test_case_ids:
                return {'error': 'No test cases specified'}
            
            # Create run
            run = request.env['qa.test.run'].create({
                'name': kwargs.get('name', 'API Run'),
                'suite_id': suite_id,
                'test_case_ids': [(6, 0, test_case_ids)],
                'environment': environment,
                'triggered_by': 'api',
            })
            
            if auto_execute:
                run.action_execute()
            
            return {
                'success': True,
                'run_id': run.id,
                'state': run.state,
            }
            
        except Exception as e:
            _logger.error(f"API error: {str(e)}")
            return {'error': str(e)}

    @http.route('/qa_test/api/run/<int:run_id>/status', type='json', auth='user', methods=['GET'])
    def api_get_run_status(self, run_id, **kwargs):
        """Get status of a test run"""
        try:
            run = request.env['qa.test.run'].browse(run_id)
            if not run.exists():
                return {'error': 'Run not found'}
            
            return {
                'run_id': run.id,
                'name': run.name,
                'state': run.state,
                'total_tests': run.total_tests,
                'passed_tests': run.passed_tests,
                'failed_tests': run.failed_tests,
                'pass_rate': run.pass_rate,
                'duration': run.duration,
            }
            
        except Exception as e:
            _logger.error(f"API error: {str(e)}")
            return {'error': str(e)}

    @http.route('/qa_test/api/run/<int:run_id>/results', type='json', auth='user', methods=['GET'])
    def api_get_run_results(self, run_id, **kwargs):
        """Get detailed results of a test run"""
        try:
            run = request.env['qa.test.run'].browse(run_id)
            if not run.exists():
                return {'error': 'Run not found'}
            
            results = []
            for result in run.result_ids:
                results.append({
                    'test_case_id': result.test_case_id.id,
                    'test_name': result.test_case_id.name,
                    'status': result.status,
                    'duration': result.duration,
                    'message': result.message,
                })
            
            return {
                'run_id': run.id,
                'results': results,
            }
            
        except Exception as e:
            _logger.error(f"API error: {str(e)}")
            return {'error': str(e)}

    @http.route('/qa_test/api/generate', type='json', auth='user', methods=['POST'])
    def api_generate_tests(self, **kwargs):
        """
        API endpoint to generate tests from specification
        
        POST /qa_test/api/generate
        {
            "spec_id": 1,
            "analyze_first": true
        }
        """
        try:
            spec_id = kwargs.get('spec_id')
            analyze_first = kwargs.get('analyze_first', True)
            
            if not spec_id:
                return {'error': 'spec_id is required'}
            
            spec = request.env['qa.test.spec'].browse(spec_id)
            if not spec.exists():
                return {'error': 'Specification not found'}
            
            if analyze_first and spec.module_id:
                spec.action_analyze_module()
            
            spec._generate_tests()
            
            return {
                'success': True,
                'spec_id': spec.id,
                'test_count': spec.test_case_count,
                'state': spec.state,
            }
            
        except Exception as e:
            _logger.error(f"API error: {str(e)}")
            return {'error': str(e)}

    @http.route('/qa_test/webhook/jenkins', type='json', auth='public', methods=['POST'], csrf=False)
    def webhook_jenkins(self, **kwargs):
        """
        Webhook endpoint for Jenkins build completion
        
        POST /qa_test/webhook/jenkins
        {
            "run_id": 1,
            "build_number": 123,
            "status": "SUCCESS",
            "results": [...]
        }
        """
        try:
            run_id = kwargs.get('run_id')
            status = kwargs.get('status')
            
            if not run_id:
                return {'error': 'run_id is required'}
            
            run = request.env['qa.test.run'].sudo().browse(int(run_id))
            if not run.exists():
                return {'error': 'Run not found'}
            
            # Map Jenkins status to our status
            status_map = {
                'SUCCESS': 'passed',
                'FAILURE': 'failed',
                'UNSTABLE': 'failed',
                'ABORTED': 'cancelled',
            }
            
            run.write({
                'state': status_map.get(status, 'error'),
                'jenkins_build_number': kwargs.get('build_number'),
            })
            
            # Process results if provided
            results = kwargs.get('results', [])
            for result_data in results:
                test_case = request.env['qa.test.case'].sudo().search([
                    ('test_id', '=', result_data.get('test_id'))
                ], limit=1)
                
                if test_case:
                    request.env['qa.test.result'].sudo().create({
                        'test_case_id': test_case.id,
                        'run_id': run.id,
                        'status': result_data.get('status', 'error'),
                        'duration': result_data.get('duration', 0),
                        'message': result_data.get('message', ''),
                    })
            
            return {'success': True}
            
        except Exception as e:
            _logger.error(f"Webhook error: {str(e)}")
            return {'error': str(e)}

    @http.route('/qa_test/dashboard/data', type='json', auth='user', methods=['GET'])
    def get_dashboard_data(self, **kwargs):
        """Get data for dashboard"""
        try:
            TestSpec = request.env['qa.test.spec']
            TestCase = request.env['qa.test.case']
            TestRun = request.env['qa.test.run']
            TestResult = request.env['qa.test.result']
            
            # Summary stats
            total_specs = TestSpec.search_count([])
            total_tests = TestCase.search_count([])
            ready_tests = TestCase.search_count([('state', '=', 'ready')])
            
            # Pass rate from recent results
            recent_results = TestResult.search([], limit=100, order='execution_date desc')
            if recent_results:
                passed = len(recent_results.filtered(lambda r: r.status == 'passed'))
                pass_rate = (passed / len(recent_results)) * 100
            else:
                pass_rate = 0
            
            # Recent runs
            recent_runs = TestRun.search([], limit=5, order='start_time desc')
            runs_data = [{
                'id': r.id,
                'name': r.name,
                'date': r.start_time.isoformat() if r.start_time else '',
                'state': r.state,
                'pass_rate': r.pass_rate,
            } for r in recent_runs]
            
            # Failed tests
            failed_tests = TestCase.search([('state', 'in', ['failed', 'error'])], limit=10)
            failed_data = [{
                'id': t.id,
                'name': t.name,
                'last_run': t.last_run_date.isoformat() if t.last_run_date else '',
                'error': (t.last_error_message or '')[:100],
            } for t in failed_tests]
            
            return {
                'total_specs': total_specs,
                'total_tests': total_tests,
                'pending_tests': ready_tests,
                'pass_rate': round(pass_rate, 1),
                'recent_runs': runs_data,
                'failed_tests': failed_data,
            }
            
        except Exception as e:
            _logger.error(f"Dashboard error: {str(e)}")
            return {'error': str(e)}
