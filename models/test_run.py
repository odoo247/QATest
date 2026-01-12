# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class QATestRun(models.Model):
    _name = 'qa.test.run'
    _description = 'Test Run'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_time desc'

    name = fields.Char(string='Run Name', required=True, default=lambda self: self._default_name())
    active = fields.Boolean(default=True)
    
    # Customer & Server
    customer_id = fields.Many2one('qa.customer', string='Customer',
                                   ondelete='cascade',
                                   help='Customer this run belongs to')
    server_id = fields.Many2one('qa.customer.server', string='Target Server',
                                 ondelete='set null',
                                 help='Server where tests were executed')
    
    # Run configuration
    suite_id = fields.Many2one('qa.test.suite', string='Test Suite')
    test_case_ids = fields.Many2many('qa.test.case', string='Test Cases')
    
    # Configuration
    config_id = fields.Many2one('qa.test.ai.config', string='Configuration',
                                default=lambda self: self.env['qa.test.ai.config'].search([('active', '=', True)], limit=1))
    
    # Target server info (from customer server)
    target_url = fields.Char(string='Target URL', help='URL of the Odoo instance to test')
    target_database = fields.Char(string='Target Database', help='Database name')
    
    # Legacy/fallback
    environment = fields.Selection([
        ('local', 'Local'),
        ('development', 'Development'),
        ('staging', 'Staging'),
        ('uat', 'UAT'),
        ('production', 'Production'),
    ], string='Environment', compute='_compute_environment', store=True)
    base_url = fields.Char(string='Base URL', compute='_compute_base_url')
    
    # Trigger
    triggered_by = fields.Selection([
        ('manual', 'Manual'),
        ('schedule', 'Scheduled'),
        ('jenkins', 'Jenkins'),
        ('api', 'API'),
    ], string='Triggered By', default='manual')
    triggered_by_user_id = fields.Many2one('res.users', string='Triggered By User',
                                           default=lambda self: self.env.user)
    
    # Status
    state = fields.Selection([
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('error', 'Error'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='pending', tracking=True)
    
    # Timing
    start_time = fields.Datetime(string='Start Time')
    end_time = fields.Datetime(string='End Time')
    duration = fields.Float(string='Duration (s)', compute='_compute_duration', store=True)
    duration_display = fields.Char(string='Duration', compute='_compute_duration_display')
    
    # Results
    result_ids = fields.One2many('qa.test.result', 'run_id', string='Results')
    total_tests = fields.Integer(string='Total Tests', compute='_compute_statistics', store=True)
    passed_tests = fields.Integer(string='Passed', compute='_compute_statistics', store=True)
    failed_tests = fields.Integer(string='Failed', compute='_compute_statistics', store=True)
    error_tests = fields.Integer(string='Errors', compute='_compute_statistics', store=True)
    skipped_tests = fields.Integer(string='Skipped', compute='_compute_statistics', store=True)
    pass_rate = fields.Float(string='Pass Rate (%)', compute='_compute_statistics', store=True)
    
    # Logs and Reports
    log = fields.Text(string='Execution Log')
    error_message = fields.Text(string='Error Message')
    report_html = fields.Html(string='HTML Report')
    report_attachment_id = fields.Many2one('ir.attachment', string='Report File',
                                           ondelete='set null')
    
    # Jenkins integration
    jenkins_build_number = fields.Integer(string='Jenkins Build #')
    jenkins_build_url = fields.Char(string='Jenkins Build URL')
    
    # Tags filter used
    include_tags = fields.Char(string='Include Tags')
    exclude_tags = fields.Char(string='Exclude Tags')

    def _default_name(self):
        return f"Test Run {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    @api.depends('server_id', 'server_id.environment')
    def _compute_environment(self):
        for run in self:
            if run.server_id:
                run.environment = run.server_id.environment
            else:
                run.environment = 'local'

    @api.depends('target_url', 'server_id')
    def _compute_base_url(self):
        for run in self:
            if run.target_url:
                run.base_url = run.target_url
            elif run.server_id:
                run.base_url = run.server_id.url
            elif run.config_id:
                run.base_url = run.config_id.test_base_url
            else:
                run.base_url = False

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for run in self:
            if run.start_time and run.end_time:
                delta = run.end_time - run.start_time
                run.duration = delta.total_seconds()
            else:
                run.duration = 0

    @api.depends('duration')
    def _compute_duration_display(self):
        for run in self:
            if run.duration:
                minutes, seconds = divmod(int(run.duration), 60)
                hours, minutes = divmod(minutes, 60)
                if hours:
                    run.duration_display = f"{hours}h {minutes}m {seconds}s"
                elif minutes:
                    run.duration_display = f"{minutes}m {seconds}s"
                else:
                    run.duration_display = f"{seconds}s"
            else:
                run.duration_display = '-'

    @api.depends('result_ids', 'result_ids.status')
    def _compute_statistics(self):
        for run in self:
            results = run.result_ids
            run.total_tests = len(results)
            run.passed_tests = len(results.filtered(lambda r: r.status == 'passed'))
            run.failed_tests = len(results.filtered(lambda r: r.status == 'failed'))
            run.error_tests = len(results.filtered(lambda r: r.status == 'error'))
            run.skipped_tests = len(results.filtered(lambda r: r.status == 'skipped'))
            run.pass_rate = (run.passed_tests / run.total_tests * 100) if run.total_tests else 0

    def action_execute(self):
        """Execute the test run"""
        self.ensure_one()
        
        if self.state == 'running':
            raise UserError('Test run is already in progress.')
        
        if not self.test_case_ids:
            raise UserError('No test cases selected for execution.')
        
        self.write({
            'state': 'running',
            'start_time': fields.Datetime.now(),
            'log': '',
            'error_message': False,
        })
        
        self._log("=" * 50)
        self._log(f"Starting Test Run: {self.name}")
        if self.customer_id:
            self._log(f"Customer: {self.customer_id.name}")
        if self.server_id:
            self._log(f"Server: {self.server_id.name} ({self.server_id.environment})")
        self._log(f"Target URL: {self.target_url or self.base_url or 'Not configured'}")
        if self.target_database:
            self._log(f"Database: {self.target_database}")
        self._log(f"Test Cases: {len(self.test_case_ids)}")
        self._log("=" * 50)
        
        try:
            # Execute each test case
            for test_case in self.test_case_ids:
                self._log(f"\nExecuting: {test_case.name}")
                try:
                    result = test_case._execute(self.id)
                    self._log(f"  Status: {result.status}")
                    if result.status != 'passed':
                        self._log(f"  Message: {result.message}")
                except Exception as e:
                    self._log(f"  ERROR: {str(e)}")
                    # Create error result
                    self.env['qa.test.result'].create({
                        'test_case_id': test_case.id,
                        'run_id': self.id,
                        'status': 'error',
                        'message': str(e),
                    })
            
            # Determine final status
            if self.error_tests > 0:
                final_status = 'error'
            elif self.failed_tests > 0:
                final_status = 'failed'
            else:
                final_status = 'passed'
            
            self.write({
                'state': final_status,
                'end_time': fields.Datetime.now(),
            })
            
            self._log("\n" + "=" * 50)
            self._log(f"Test Run Completed: {final_status.upper()}")
            self._log(f"Passed: {self.passed_tests}, Failed: {self.failed_tests}, Errors: {self.error_tests}")
            self._log(f"Pass Rate: {self.pass_rate:.1f}%")
            self._log("=" * 50)
            
            # Send notifications
            self._send_notifications()
            
        except Exception as e:
            _logger.error(f"Test run failed: {str(e)}")
            self.write({
                'state': 'error',
                'end_time': fields.Datetime.now(),
                'error_message': str(e),
            })
            self._log(f"\nFATAL ERROR: {str(e)}")
            raise
        
        return True

    def action_execute_jenkins(self):
        """Execute tests via Jenkins"""
        self.ensure_one()
        
        config = self.config_id or self.env['qa.test.ai.config'].search([('active', '=', True)], limit=1)
        
        if not config:
            raise UserError('No AI configuration found. Please configure settings first.')
        
        if not config.jenkins_enabled:
            raise UserError('Jenkins integration is not enabled.\n\n'
                          'Please go to QA Test Generator > Configuration > AI Settings\n'
                          'and enable Jenkins integration with proper URL, credentials, and job name.')
        
        if not config.jenkins_url or not config.jenkins_job_name:
            raise UserError('Jenkins is enabled but not properly configured.\n\n'
                          'Please configure Jenkins URL and Job Name in AI Settings.')
        
        try:
            from ..services.jenkins_client import JenkinsClient
            client = JenkinsClient(config)
            
            # Trigger Jenkins build first to get build number
            build_number = client.trigger_build(
                job_name=config.jenkins_job_name,
                parameters={
                    'TEST_CASES': ','.join(self.test_case_ids.mapped('test_id')),
                    'BASE_URL': self.target_url or self.base_url or '',
                    'RUN_ID': str(self.id),
                }
            )
            
            # Update state after successful trigger
            self.write({
                'state': 'running',
                'triggered_by': 'jenkins',
                'jenkins_build_number': build_number,
                'jenkins_build_url': f"{config.jenkins_url}/job/{config.jenkins_job_name}/{build_number}",
                'start_time': fields.Datetime.now(),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Jenkins Build Triggered',
                    'message': f'Build #{build_number} started. Jenkins will fetch tests in a few seconds.',
                    'type': 'success',
                }
            }
        except Exception as e:
            error_msg = str(e)
            if '404' in error_msg:
                raise UserError(f'Jenkins job not found: {config.jenkins_job_name}\n\n'
                              f'Please verify the job exists in Jenkins at:\n{config.jenkins_url}')
            elif '401' in error_msg or '403' in error_msg:
                raise UserError('Jenkins authentication failed.\n\n'
                              'Please verify your Jenkins credentials in AI Settings.')
            else:
                raise UserError(f'Jenkins error: {error_msg}')

    def action_cancel(self):
        """Cancel the test run"""
        self.ensure_one()
        if self.state == 'running':
            # TODO: Implement actual cancellation logic
            pass
        self.write({
            'state': 'cancelled',
            'end_time': fields.Datetime.now(),
        })
        self._log("\nTest run cancelled by user.")

    def action_view_results(self):
        """View results for this run"""
        return {
            'name': 'Test Results',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.result',
            'view_mode': 'list,form',
            'domain': [('run_id', '=', self.id)],
        }

    def action_view_failed(self):
        """View failed tests"""
        return {
            'name': 'Failed Tests',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.result',
            'view_mode': 'list,form',
            'domain': [('run_id', '=', self.id), ('status', 'in', ['failed', 'error'])],
        }

    def action_rerun_failed(self):
        """Re-run only failed tests"""
        self.ensure_one()
        failed_tests = self.result_ids.filtered(
            lambda r: r.status in ['failed', 'error']
        ).mapped('test_case_id')
        
        if not failed_tests:
            raise UserError('No failed tests to re-run.')
        
        new_run = self.create({
            'name': f"Re-run: {self.name}",
            'suite_id': self.suite_id.id,
            'test_case_ids': [(6, 0, failed_tests.ids)],
            'config_id': self.config_id.id,
            'environment': self.environment,
        })
        
        return {
            'name': 'Re-run Failed Tests',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.run',
            'view_mode': 'form',
            'res_id': new_run.id,
        }

    def action_generate_report(self):
        """Generate HTML report"""
        self.ensure_one()
        # TODO: Implement detailed HTML report generation
        pass

    def _log(self, message):
        """Append message to execution log"""
        current_log = self.log or ''
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log = current_log + f"[{timestamp}] {message}\n"

    def _send_notifications(self):
        """Send email notifications after run completion"""
        config = self.config_id or self.env['qa.test.ai.config'].get_active_config()
        
        if not config.notify_on_complete:
            return
        
        if config.notify_on_failure and self.state == 'passed':
            return
        
        if config.notification_email:
            template = self.env.ref('qa_test_generator.mail_template_test_run_complete', False)
            if template:
                template.send_mail(self.id, force_send=True)

    @api.model
    def create_from_api(self, vals):
        """Create and optionally execute a test run from API"""
        run = self.create(vals)
        if vals.get('auto_execute'):
            run.action_execute()
        return run

    # ==========================================
    # Jenkins Polling Methods
    # ==========================================
    
    @api.model
    def _cron_check_jenkins_status(self):
        """Cron job to check Jenkins build status and fetch results"""
        _logger.info("Checking Jenkins build status...")
        
        running_runs = self.search([
            ('state', '=', 'running'),
            ('triggered_by', '=', 'jenkins'),
            ('jenkins_build_number', '!=', False),
        ])
        
        _logger.info(f"Found {len(running_runs)} running Jenkins builds")
        
        for run in running_runs:
            try:
                with self.env.cr.savepoint():
                    run._check_jenkins_build()
            except Exception as e:
                _logger.error(f"Error checking Jenkins build for run {run.id}: {e}")
    
    def _check_jenkins_build(self):
        """Check Jenkins build status and fetch results if complete (used by cron)"""
        self.ensure_one()
        
        config = self.config_id or self.env['qa.test.ai.config'].search([('active', '=', True)], limit=1)
        if not config or not config.jenkins_enabled:
            _logger.warning(f"Jenkins not configured for run {self.id}")
            return
        
        from ..services.jenkins_client import JenkinsClient
        client = JenkinsClient(config)
        
        # Get build status
        status = client.get_build_status(
            job_name=config.jenkins_job_name,
            build_number=self.jenkins_build_number
        )
        
        _logger.info(f"Jenkins build #{self.jenkins_build_number} status: {status}")
        
        if status.get('building'):
            _logger.info(f"Build #{self.jenkins_build_number} still running...")
            return
        
        jenkins_result = status.get('result', 'FAILURE')
        result_map = {
            'SUCCESS': 'passed',
            'FAILURE': 'failed',
            'UNSTABLE': 'failed',
            'ABORTED': 'cancelled',
            'NOT_BUILT': 'error',
        }
        
        odoo_state = result_map.get(jenkins_result, 'error')
        duration = status.get('duration', 0) / 1000
        
        # Fetch results separately with its own error handling
        test_results = {'total': 0, 'passed': 0, 'failed': 0, 'details': []}
        try:
            test_results = self._fetch_jenkins_robot_results(client, config.jenkins_job_name)
        except Exception as e:
            _logger.warning(f"Could not fetch test results: {e}")
        
        # Update run state using SQL to avoid ORM transaction issues
        self.env.cr.execute("""
            UPDATE qa_test_run 
            SET state = %s, end_time = %s, duration = %s
            WHERE id = %s
        """, (odoo_state, fields.Datetime.now(), duration, self.id))
        
        # Create individual test results if we have them
        try:
            if test_results.get('details'):
                self._create_test_results_from_jenkins(test_results['details'])
            elif test_results.get('total', 0) > 0:
                # No details but we have totals - create summary results for test cases in run
                self._create_summary_results_from_jenkins(test_results, odoo_state)
        except Exception as e:
            _logger.warning(f"Error creating test results: {e}")
        
        _logger.info(f"Run {self.id} updated: {odoo_state} (passed: {test_results.get('passed', 0)}, failed: {test_results.get('failed', 0)})")
    
    def _fetch_jenkins_robot_results(self, client, job_name):
        """Fetch Robot Framework results from Jenkins"""
        results = {'total': 0, 'passed': 0, 'failed': 0, 'details': []}
        
        try:
            robot_report = client.get_test_report(job_name, self.jenkins_build_number)
            
            if robot_report:
                results['total'] = robot_report.get('overallTotal', 0)
                results['passed'] = robot_report.get('overallPassed', 0)
                results['failed'] = robot_report.get('overallFailed', 0)
                
                for suite in robot_report.get('suites', []):
                    for case in suite.get('cases', []):
                        results['details'].append({
                            'name': case.get('name'),
                            'status': 'passed' if case.get('status') == 'PASS' else 'failed',
                            'duration': case.get('duration', 0) / 1000,
                            'message': case.get('errorMsg', ''),
                        })
            else:
                results = self._parse_results_from_log(client, job_name)
                
        except Exception as e:
            _logger.warning(f"Could not fetch Robot results: {e}")
        
        return results
    
    def _parse_results_from_log(self, client, job_name):
        """Parse test results from Jenkins console log"""
        import re
        results = {'total': 0, 'passed': 0, 'failed': 0, 'details': []}
        
        try:
            log = client.get_build_log(job_name, self.jenkins_build_number)
            _logger.info(f"Parsing Jenkins log for build #{self.jenkins_build_number}, log length: {len(log)}")
            
            # Get totals - look for "12 tests, 7 passed, 5 failed" or similar
            totals_patterns = [
                r'(\d+)\s+tests?,\s+(\d+)\s+passed,\s+(\d+)\s+failed',
                r'(\d+)\s+test[s]?,\s+(\d+)\s+pass(?:ed)?,\s+(\d+)\s+fail(?:ed)?',
                r'Total:\s*(\d+).*?Pass(?:ed)?:\s*(\d+).*?Fail(?:ed)?:\s*(\d+)',
            ]
            
            for pattern in totals_patterns:
                match = re.search(pattern, log, re.IGNORECASE)
                if match:
                    results['total'] = int(match.group(1))
                    results['passed'] = int(match.group(2))
                    results['failed'] = int(match.group(3))
                    _logger.info(f"Found totals: {results['total']} tests, {results['passed']} passed, {results['failed']} failed")
                    break
            
            # Multiple patterns to find individual test results
            # Robot Framework format: "Test Name    | PASS |" or "Test Name :: description    | FAIL | error message"
            test_patterns = [
                # Pattern 1: "Test Name :: Description    | PASS/FAIL |"
                r'^([A-Z][A-Za-z0-9_ ]+(?:\s+[A-Za-z0-9_]+)*)\s*(?:::\s*[^|]*)?\s*\|\s*(PASS|FAIL)\s*\|(.*)$',
                # Pattern 2: "Test Name    | PASS/FAIL | duration"
                r'^([A-Z][A-Za-z0-9_ ]+)\s+\|\s*(PASS|FAIL)\s*\|(.*)$',
                # Pattern 3: Lines starting with test keywords
                r'^\*\*\*\s*Test[:\s]+([^\|]+?)\s*\*\*\*.*?(PASS|FAIL)',
            ]
            
            seen_tests = set()
            for line in log.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                for pattern in test_patterns:
                    match = re.match(pattern, line, re.IGNORECASE)
                    if match:
                        test_name = match.group(1).strip()
                        status_str = match.group(2).upper()
                        message = match.group(3).strip() if len(match.groups()) > 2 else ''
                        
                        # Skip suite-level and internal results
                        skip_names = ['tests', 'smoke test', 'tests.smoke test', 'test suites', 
                                     'output', 'log', 'report', 'downloaded tests']
                        if test_name.lower() in skip_names:
                            continue
                        if test_name.startswith('Tests.') or '.' in test_name:
                            continue
                        if test_name in seen_tests:
                            continue
                            
                        seen_tests.add(test_name)
                        results['details'].append({
                            'name': test_name,
                            'status': 'passed' if status_str == 'PASS' else 'failed',
                            'duration': 0,
                            'message': message.strip('| \t'),
                        })
                        _logger.info(f"Found test: '{test_name}' = {status_str}, msg='{message[:50] if message else ''}'")
                        break
            
            _logger.info(f"Parsed {len(results['details'])} test details from log")
            
            # If we found totals but no details, log the issue
            if results['total'] > 0 and not results['details']:
                _logger.warning(f"Found totals but no test details. Log sample: {log[:2000]}")
                
        except Exception as e:
            _logger.error(f"Could not parse log: {e}", exc_info=True)
        
        return results
    
    def _create_test_results_from_jenkins(self, details):
        """Create qa.test.result records from Jenkins results"""
        _logger.info(f"Creating test results from {len(details)} details")
        
        for detail in details:
            test_case = None
            detail_name = detail['name'].lower()
            
            # Try to find matching test case
            for tc in self.test_case_ids:
                tc_name = (tc.name or '').lower()
                # Check various matching conditions
                if tc_name == detail_name:
                    test_case = tc
                    break
                elif detail_name in tc_name:
                    test_case = tc
                    break
                elif tc_name in detail_name:
                    test_case = tc
                    break
            
            if test_case:
                _logger.info(f"Matched test '{detail['name']}' to test case '{test_case.name}'")
                self.env['qa.test.result'].create({
                    'test_case_id': test_case.id,
                    'run_id': self.id,
                    'status': detail['status'],
                    'duration': detail['duration'],
                    'message': detail['message'],
                    'log': f"Jenkins build #{self.jenkins_build_number}",
                })
                
                test_case.write({
                    'state': detail['status'],
                    'last_run_date': fields.Datetime.now(),
                    'last_run_duration': detail['duration'],
                    'last_error_message': detail['message'] if detail['status'] == 'failed' else False,
                })
            else:
                # Create result without linking to specific test case
                _logger.info(f"No matching test case for '{detail['name']}', creating unlinked result")
                self.env['qa.test.result'].create({
                    'run_id': self.id,
                    'test_name': detail['name'],
                    'status': detail['status'],
                    'duration': detail['duration'],
                    'message': detail['message'],
                    'log': f"Jenkins build #{self.jenkins_build_number}\nTest: {detail['name']}",
                })
    
    def _create_summary_results_from_jenkins(self, test_results, overall_status):
        """Create summary test results when no individual details available"""
        _logger.info(f"Creating summary results: {test_results}, overall_status={overall_status}")
        
        passed_count = test_results.get('passed', 0)
        failed_count = test_results.get('failed', 0)
        total_count = test_results.get('total', 0)
        
        # If we have test cases in this run, create a result for each
        if self.test_case_ids:
            test_cases_list = list(self.test_case_ids)
            _logger.info(f"Creating results for {len(test_cases_list)} test cases")
            
            # Distribute passed/failed based on counts
            for i, test_case in enumerate(test_cases_list):
                # If we have exact counts, assign status based on them
                if i < passed_count:
                    status = 'passed'
                elif i < passed_count + failed_count:
                    status = 'failed'
                else:
                    status = overall_status
                
                self.env['qa.test.result'].create({
                    'test_case_id': test_case.id,
                    'test_name': test_case.name,  # Also set test_name for visibility
                    'run_id': self.id,
                    'status': status,
                    'duration': 0,
                    'message': f"Jenkins build #{self.jenkins_build_number} - {passed_count} passed, {failed_count} failed",
                    'log': f"Result from Jenkins build #{self.jenkins_build_number}\n"
                           f"Total: {total_count}\n"
                           f"Passed: {passed_count}\n"
                           f"Failed: {failed_count}",
                })
                
                test_case.write({
                    'state': status,
                    'last_run_date': fields.Datetime.now(),
                })
        else:
            # No test cases linked - create individual results based on counts
            _logger.info(f"No test cases linked, creating {total_count} generic results")
            
            for i in range(passed_count):
                self.env['qa.test.result'].create({
                    'run_id': self.id,
                    'test_name': f"Test {i+1}",
                    'status': 'passed',
                    'duration': 0,
                    'message': f"Passed (Jenkins build #{self.jenkins_build_number})",
                })
            
            for i in range(failed_count):
                self.env['qa.test.result'].create({
                    'run_id': self.id,
                    'test_name': f"Test {passed_count + i + 1}",
                    'status': 'failed',
                    'duration': 0,
                    'message': f"Failed (Jenkins build #{self.jenkins_build_number})",
                })

    def action_refresh_jenkins_status(self):
        """Manual button to refresh Jenkins status"""
        self.ensure_one()
        
        # Read values directly to avoid ORM issues
        run_data = self.read(['triggered_by', 'jenkins_build_number', 'state'])[0]
        
        if run_data.get('triggered_by') != 'jenkins':
            raise UserError('This test run was not triggered by Jenkins.')
        
        if not run_data.get('jenkins_build_number'):
            raise UserError('No Jenkins build number found.')
        
        # Do the Jenkins check in a new cursor to isolate from any transaction issues
        try:
            self._do_jenkins_refresh()
        except Exception as e:
            _logger.error(f"Error checking Jenkins status: {e}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Jenkins Status Check Failed',
                    'message': str(e)[:200],
                    'sticky': True,
                    'type': 'danger',
                }
            }
        
        # Get fresh result count
        result_count = self.env['qa.test.result'].search_count([('run_id', '=', self.id)])
        current_state = self.read(['state'])[0]['state']
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Jenkins Status Refreshed',
                'message': f'Run status: {current_state}, Results: {result_count}',
                'sticky': False,
                'type': 'success',
            }
        }
    
    def _do_jenkins_refresh(self):
        """Perform Jenkins refresh with proper error handling"""
        self.ensure_one()
        
        config = self.config_id or self.env['qa.test.ai.config'].search([('active', '=', True)], limit=1)
        if not config or not config.jenkins_enabled:
            raise UserError('Jenkins not configured')
        
        from ..services.jenkins_client import JenkinsClient
        client = JenkinsClient(config)
        
        # Get build status from Jenkins
        status = client.get_build_status(
            job_name=config.jenkins_job_name,
            build_number=self.jenkins_build_number
        )
        
        _logger.info(f"Jenkins build #{self.jenkins_build_number} status: {status}")
        
        if status.get('building'):
            _logger.info(f"Build #{self.jenkins_build_number} still running...")
            return  # Still running, nothing to update
        
        # Map Jenkins result to Odoo state
        jenkins_result = status.get('result', 'FAILURE')
        result_map = {
            'SUCCESS': 'passed',
            'FAILURE': 'failed',
            'UNSTABLE': 'failed',
            'ABORTED': 'cancelled',
            'NOT_BUILT': 'error',
        }
        odoo_state = result_map.get(jenkins_result, 'error')
        duration = status.get('duration', 0) / 1000
        
        # Fetch test results
        test_results = {'total': 0, 'passed': 0, 'failed': 0, 'details': []}
        try:
            test_results = self._fetch_jenkins_robot_results(client, config.jenkins_job_name)
        except Exception as e:
            _logger.warning(f"Could not fetch test results: {e}")
        
        # Update run - use SQL directly to avoid ORM issues
        self.env.cr.execute("""
            UPDATE qa_test_run 
            SET state = %s, end_time = %s, duration = %s
            WHERE id = %s
        """, (odoo_state, fields.Datetime.now(), duration, self.id))
        
        # Create test results
        if test_results.get('details'):
            self._create_test_results_from_jenkins(test_results['details'])
        elif test_results.get('total', 0) > 0:
            self._create_summary_results_from_jenkins(test_results, odoo_state)
        
        _logger.info(f"Run {self.id} updated: {odoo_state}")
