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
            
            # Trigger Jenkins build
            build_number = client.trigger_build(
                job_name=config.jenkins_job_name,
                parameters={
                    'TEST_CASES': ','.join(self.test_case_ids.mapped('test_id')),
                    'BASE_URL': self.target_url or self.base_url or '',
                    'RUN_ID': str(self.id),
                }
            )
            
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
                    'message': f'Build #{build_number} started.',
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
                run._check_jenkins_build()
            except Exception as e:
                _logger.error(f"Error checking Jenkins build for run {run.id}: {e}")
    
    def _check_jenkins_build(self):
        """Check Jenkins build status and fetch results if complete"""
        self.ensure_one()
        
        config = self.config_id or self.env['qa.test.ai.config'].search([('active', '=', True)], limit=1)
        if not config or not config.jenkins_enabled:
            _logger.warning(f"Jenkins not configured for run {self.id}")
            return
        
        from ..services.jenkins_client import JenkinsClient
        client = JenkinsClient(config)
        
        try:
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
            
            test_results = self._fetch_jenkins_robot_results(client, config.jenkins_job_name)
            
            # Update run state and timing
            self.write({
                'state': odoo_state,
                'end_time': fields.Datetime.now(),
                'duration': duration,
            })
            
            # Create individual test results if we have them
            # This will trigger recomputation of total_tests, passed_tests, failed_tests
            if test_results.get('details'):
                self._create_test_results_from_jenkins(test_results['details'])
            
            _logger.info(f"Run {self.id} updated: {odoo_state} (passed: {test_results.get('passed', 0)}, failed: {test_results.get('failed', 0)})")
            
        except Exception as e:
            _logger.error(f"Failed to check Jenkins build: {e}")
    
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
            
            match = re.search(r'(\d+)\s+tests?,\s+(\d+)\s+passed,\s+(\d+)\s+failed', log)
            if match:
                results['total'] = int(match.group(1))
                results['passed'] = int(match.group(2))
                results['failed'] = int(match.group(3))
                
        except Exception as e:
            _logger.warning(f"Could not parse log: {e}")
        
        return results
    
    def _create_test_results_from_jenkins(self, details):
        """Create qa.test.result records from Jenkins results"""
        for detail in details:
            test_case = None
            for tc in self.test_case_ids:
                if tc.name == detail['name'] or detail['name'] in (tc.name or ''):
                    test_case = tc
                    break
            
            if test_case:
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
    
    def action_refresh_jenkins_status(self):
        """Manual button to refresh Jenkins status"""
        self.ensure_one()
        if self.triggered_by == 'jenkins' and self.state == 'running':
            self._check_jenkins_build()
        return True
