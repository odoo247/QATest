# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class QATestSuite(models.Model):
    _name = 'qa.test.suite'
    _description = 'Test Suite'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'customer_id, sequence, name'

    name = fields.Char(string='Suite Name', required=True, tracking=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
    
    # Customer
    customer_id = fields.Many2one('qa.customer', string='Customer',
                                   ondelete='cascade',
                                   help='Customer this suite belongs to')
    
    # Code Scan (for code-first generation)
    code_scan_id = fields.Many2one('qa.code.scan', string='Code Scan',
                                    ondelete='set null',
                                    help='Code scan that generated this suite')
    scanned_module_id = fields.Many2one('qa.scanned.module', string='Scanned Module',
                                         ondelete='set null')
    
    description = fields.Text(string='Description')
    
    # Relations
    spec_ids = fields.One2many('qa.test.spec', 'suite_id', string='Test Specifications')
    test_case_ids = fields.One2many('qa.test.case', 'suite_id', string='Test Cases')
    run_ids = fields.One2many('qa.test.run', 'suite_id', string='Test Runs')
    
    # Computed counts
    spec_count = fields.Integer(string='Spec Count', compute='_compute_counts')
    test_case_count = fields.Integer(string='Test Count', compute='_compute_counts')
    run_count = fields.Integer(string='Run Count', compute='_compute_counts')
    
    # Suite settings
    parallel_execution = fields.Boolean(string='Parallel Execution', default=False,
                                        help='Run tests in parallel (requires multiple workers)')
    max_workers = fields.Integer(string='Max Workers', default=4)
    fail_fast = fields.Boolean(string='Fail Fast', default=False,
                               help='Stop execution on first failure')
    
    # Tags to include/exclude
    include_tags = fields.Char(string='Include Tags',
                               help='Comma-separated tags to include (e.g., smoke,critical)')
    exclude_tags = fields.Char(string='Exclude Tags',
                               help='Comma-separated tags to exclude (e.g., slow,manual)')
    
    # Output settings
    output_dir = fields.Char(string='Output Directory',
                             help='Custom output directory for this suite')
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('running', 'Running'),
        ('completed', 'Completed'),
    ], string='Status', default='draft', compute='_compute_state', store=True)
    
    # Last run info
    last_run_id = fields.Many2one('qa.test.run', string='Last Run', 
                                  compute='_compute_last_run')
    last_run_date = fields.Datetime(string='Last Run Date', 
                                    compute='_compute_last_run')
    last_run_status = fields.Selection([
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('error', 'Error'),
    ], string='Last Run Status', compute='_compute_last_run')
    pass_rate = fields.Float(string='Pass Rate (%)', compute='_compute_last_run')
    
    # Schedule
    scheduled = fields.Boolean(string='Scheduled', default=False)
    cron_id = fields.Many2one('ir.cron', string='Scheduled Job', readonly=True,
                               ondelete='set null')
    schedule_interval = fields.Selection([
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ], string='Schedule Interval', default='daily')
    schedule_time = fields.Float(string='Schedule Time (24h)', default=6.0,
                                 help='Time to run in 24-hour format (e.g., 6.5 = 6:30 AM)')

    @api.depends('spec_ids', 'test_case_ids', 'run_ids')
    def _compute_counts(self):
        for record in self:
            record.spec_count = len(record.spec_ids)
            record.test_case_count = len(record.test_case_ids)
            record.run_count = len(record.run_ids)

    @api.depends('test_case_ids', 'test_case_ids.state')
    def _compute_state(self):
        for record in self:
            if not record.test_case_ids:
                record.state = 'draft'
            elif all(tc.state == 'ready' for tc in record.test_case_ids):
                record.state = 'ready'
            else:
                record.state = 'draft'

    @api.depends('run_ids')
    def _compute_last_run(self):
        for record in self:
            last_run = record.run_ids.sorted('start_time', reverse=True)[:1]
            record.last_run_id = last_run.id if last_run else False
            record.last_run_date = last_run.start_time if last_run else False
            record.last_run_status = last_run.state if last_run else False
            record.pass_rate = last_run.pass_rate if last_run else 0.0

    def action_run_suite(self):
        """Run all tests in this suite"""
        self.ensure_one()
        if not self.test_case_ids:
            raise UserError('No test cases in this suite. Generate tests first.')
        
        return {
            'name': 'Run Test Suite',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.run.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_suite_id': self.id,
                'default_test_case_ids': [(6, 0, self.test_case_ids.ids)],
            }
        }

    def action_view_specs(self):
        """View specifications in this suite"""
        return {
            'name': 'Test Specifications',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.spec',
            'view_mode': 'list,form',
            'domain': [('suite_id', '=', self.id)],
            'context': {'default_suite_id': self.id},
        }

    def action_view_test_cases(self):
        """View test cases in this suite"""
        return {
            'name': 'Test Cases',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.case',
            'view_mode': 'list,form',
            'domain': [('suite_id', '=', self.id)],
            'context': {'default_suite_id': self.id},
        }

    def action_view_runs(self):
        """View test runs for this suite"""
        return {
            'name': 'Test Runs',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.run',
            'view_mode': 'list,form',
            'domain': [('suite_id', '=', self.id)],
            'context': {'default_suite_id': self.id},
        }

    def action_generate_all_tests(self):
        """Generate tests for all specifications in this suite"""
        self.ensure_one()
        if not self.spec_ids:
            raise UserError('No specifications in this suite.')
        
        return {
            'name': 'Generate Tests',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_spec_ids': [(6, 0, self.spec_ids.ids)],
            }
        }

    def action_export_robot_files(self):
        """Export all tests as Robot Framework files"""
        self.ensure_one()
        if not self.test_case_ids:
            raise UserError('No test cases to export.')
        
        from ..services.robot_generator import RobotGenerator
        config = self.env['qa.test.ai.config'].get_active_config()
        generator = RobotGenerator(config)
        
        # Generate files
        file_paths = generator.export_suite(self)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Export Complete',
                'message': f'Exported {len(file_paths)} test files.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_enable_schedule(self):
        """Enable scheduled execution"""
        self.ensure_one()
        if self.cron_id:
            self.cron_id.write({'active': True})
        else:
            # Create cron job
            interval_mapping = {
                'hourly': ('hours', 1),
                'daily': ('days', 1),
                'weekly': ('weeks', 1),
                'monthly': ('months', 1),
            }
            interval_type, interval_number = interval_mapping.get(
                self.schedule_interval, ('days', 1)
            )
            
            cron = self.env['ir.cron'].create({
                'name': f'QA Test Suite: {self.name}',
                'model_id': self.env.ref('qa_test_generator.model_qa_test_suite').id,
                'state': 'code',
                'code': f'model.browse({self.id}).action_scheduled_run()',
                'interval_type': interval_type,
                'interval_number': interval_number,
                'active': True,
            })
            self.cron_id = cron.id
        
        self.scheduled = True

    def action_disable_schedule(self):
        """Disable scheduled execution"""
        self.ensure_one()
        if self.cron_id:
            self.cron_id.write({'active': False})
        self.scheduled = False

    def action_scheduled_run(self):
        """Called by cron to run tests"""
        self.ensure_one()
        _logger.info(f"Starting scheduled run for suite: {self.name}")
        
        # Create a new test run
        run = self.env['qa.test.run'].create({
            'suite_id': self.id,
            'name': f'{self.name} - Scheduled Run',
            'test_case_ids': [(6, 0, self.test_case_ids.ids)],
            'triggered_by': 'schedule',
        })
        
        # Execute the run
        run.action_execute()
        
        return run
