# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class QATestRunWizard(models.TransientModel):
    _name = 'qa.test.run.wizard'
    _description = 'Run Tests Wizard'

    name = fields.Char(string='Run Name', default=lambda self: self._default_name())
    
    # Customer & Server - key fields
    customer_id = fields.Many2one('qa.customer', string='Customer',
                                   help='Customer whose tests to run')
    server_id = fields.Many2one('qa.customer.server', string='Target Server',
                                 domain="[('customer_id', '=', customer_id)]",
                                 help='Server to run tests against')
    
    # Suite and tests
    suite_id = fields.Many2one('qa.test.suite', string='Test Suite',
                                domain="[('customer_id', '=', customer_id)]")
    test_case_ids = fields.Many2many('qa.test.case', string='Test Cases',
                                      domain="[('customer_id', '=', customer_id)]")
    
    # Configuration
    config_id = fields.Many2one('qa.test.ai.config', string='Configuration',
                                default=lambda self: self.env['qa.test.ai.config'].search([('active', '=', True)], limit=1))
    
    # Server info (from selected server)
    base_url = fields.Char(string='Base URL', compute='_compute_server_info', store=True, readonly=False)
    database = fields.Char(string='Database', compute='_compute_server_info', store=True, readonly=False)
    environment = fields.Selection(related='server_id.environment', string='Environment', readonly=True)
    
    # Options
    execution_mode = fields.Selection([
        ('local', 'Run Locally'),
        ('jenkins', 'Run via Jenkins'),
    ], string='Execution Mode', default='local')
    headless = fields.Boolean(string='Headless Mode', default=True)
    parallel = fields.Boolean(string='Parallel Execution', default=False)
    fail_fast = fields.Boolean(string='Stop on First Failure', default=False)
    
    # Filters
    include_tags = fields.Char(string='Include Tags',
                               help='Only run tests with these tags (comma-separated)')
    exclude_tags = fields.Char(string='Exclude Tags',
                               help='Skip tests with these tags (comma-separated)')
    
    # Result
    run_id = fields.Many2one('qa.test.run', string='Created Run', readonly=True)

    def _default_name(self):
        from datetime import datetime
        return f"Test Run {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    @api.depends('server_id')
    def _compute_server_info(self):
        for record in self:
            if record.server_id:
                record.base_url = record.server_id.url
                record.database = record.server_id.database
            else:
                record.base_url = False
                record.database = False

    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        """When customer changes, reset server and auto-select default"""
        self.server_id = False
        self.suite_id = False
        self.test_case_ids = [(5, 0, 0)]  # Clear
        
        if self.customer_id:
            # Auto-select first server (prefer staging/uat)
            servers = self.customer_id.server_ids.sorted(
                lambda s: {'staging': 0, 'uat': 1, 'development': 2, 'production': 3}.get(s.environment, 4)
            )
            if servers:
                self.server_id = servers[0]

    @api.onchange('suite_id')
    def _onchange_suite_id(self):
        if self.suite_id:
            self.test_case_ids = self.suite_id.test_case_ids
            self.include_tags = self.suite_id.include_tags
            self.exclude_tags = self.suite_id.exclude_tags
            # Also set customer from suite if not set
            if not self.customer_id and self.suite_id.customer_id:
                self.customer_id = self.suite_id.customer_id

    def action_run(self):
        """Create and execute test run"""
        self.ensure_one()
        
        if not self.test_case_ids:
            raise UserError('Please select at least one test case.')
        
        if not self.server_id:
            raise UserError('Please select a target server to run tests against.')
        
        if not self.base_url:
            raise UserError('Server URL is not configured. Please check server settings.')
        
        # Validate Jenkins configuration if Jenkins mode selected
        if self.execution_mode == 'jenkins':
            config = self.config_id or self.env['qa.test.ai.config'].search([('active', '=', True)], limit=1)
            if not config or not config.jenkins_enabled:
                raise UserError('Jenkins execution mode selected but Jenkins is not enabled.\n\n'
                              'Please either:\n'
                              '1. Select "Run Locally" execution mode, or\n'
                              '2. Enable and configure Jenkins in QA Test Generator > Configuration > AI Settings')
        
        # Filter test cases by tags if specified
        test_cases = self._filter_tests_by_tags()
        
        if not test_cases:
            raise UserError('No test cases match the tag filters.')
        
        # Create test run with customer/server info
        run = self.env['qa.test.run'].create({
            'name': self.name,
            'customer_id': self.customer_id.id if self.customer_id else False,
            'server_id': self.server_id.id,
            'suite_id': self.suite_id.id if self.suite_id else False,
            'test_case_ids': [(6, 0, test_cases.ids)],
            'config_id': self.config_id.id if self.config_id else False,
            'target_url': self.base_url,
            'target_database': self.database,
            'include_tags': self.include_tags,
            'exclude_tags': self.exclude_tags,
            'triggered_by': 'manual',
        })
        
        self.run_id = run.id
        
        # Execute based on mode
        if self.execution_mode == 'jenkins':
            run.action_execute_jenkins()
        else:
            run.action_execute()
        
        # Return to run form
        return {
            'name': 'Test Run',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.run',
            'res_id': run.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def _filter_tests_by_tags(self):
        """Filter test cases by include/exclude tags"""
        test_cases = self.test_case_ids
        
        if self.include_tags:
            include_list = [t.strip() for t in self.include_tags.split(',')]
            test_cases = test_cases.filtered(
                lambda tc: any(tag in (tc.tags or '') for tag in include_list)
            )
        
        if self.exclude_tags:
            exclude_list = [t.strip() for t in self.exclude_tags.split(',')]
            test_cases = test_cases.filtered(
                lambda tc: not any(tag in (tc.tags or '') for tag in exclude_list)
            )
        
        return test_cases
    
    def action_select_all(self):
        """Select all available test cases for customer"""
        if self.customer_id:
            all_tests = self.env['qa.test.case'].search([
                ('customer_id', '=', self.customer_id.id),
                ('state', '=', 'ready')
            ])
        else:
            all_tests = self.env['qa.test.case'].search([('state', '=', 'ready')])
        self.test_case_ids = all_tests
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_select_failed(self):
        """Select only failed test cases"""
        domain = [('state', 'in', ['failed', 'error'])]
        if self.customer_id:
            domain.append(('customer_id', '=', self.customer_id.id))
        failed_tests = self.env['qa.test.case'].search(domain)
        self.test_case_ids = failed_tests
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
