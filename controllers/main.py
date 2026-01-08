# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class QATestController(http.Controller):
    """Controller for QA Test Generator API endpoints"""

    @http.route('/qa_test/api/run', type='json', auth='user', methods=['POST'])
    def api_create_run(self, **kwargs):
        """
        API endpoint to create and execute a test run
        
        POST /qa_test/api/run
        {
            "suite_id": 1,  # or
            "test_case_ids": [1, 2, 3],
            "environment": "staging",
            "auto_execute": true
        }
        """
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
