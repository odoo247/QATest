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
    
    # Environment
    config_id = fields.Many2one('qa.test.ai.config', string='Configuration',
                                default=lambda self: self.env['qa.test.ai.config'].search([], limit=1))
    environment = fields.Selection([
        ('local', 'Local'),
        ('staging', 'Staging'),
        ('production', 'Production'),
    ], string='Environment', default='local')
    base_url = fields.Char(string='Base URL', related='config_id.test_base_url')
    
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
    duration = fields.Float(string='Duration (s)', compute='_compute_duration')
    duration_display = fields.Char(string='Duration', compute='_compute_duration_display')
    
    # Results
    result_ids = fields.One2many('qa.test.result', 'run_id', string='Results')
    total_tests = fields.Integer(string='Total Tests', compute='_compute_statistics')
    passed_tests = fields.Integer(string='Passed', compute='_compute_statistics')
    failed_tests = fields.Integer(string='Failed', compute='_compute_statistics')
    error_tests = fields.Integer(string='Errors', compute='_compute_statistics')
    skipped_tests = fields.Integer(string='Skipped', compute='_compute_statistics')
    pass_rate = fields.Float(string='Pass Rate (%)', compute='_compute_statistics')
    
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
        self._log(f"Environment: {self.base_url}")
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
        
        config = self.config_id or self.env['qa.test.ai.config'].get_active_config()
        if not config.jenkins_enabled:
            raise UserError('Jenkins integration is not enabled.')
        
        from ..services.jenkins_client import JenkinsClient
        client = JenkinsClient(config)
        
        # Trigger Jenkins build
        build_number = client.trigger_build(
            job_name=config.jenkins_job_name,
            parameters={
                'TEST_CASES': ','.join(self.test_case_ids.mapped('test_id')),
                'BASE_URL': self.base_url,
                'RUN_ID': self.id,
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
        
        if config.notify_on_failure_only and self.state == 'passed':
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
