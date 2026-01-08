# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class QATestRunWizard(models.TransientModel):
    _name = 'qa.test.run.wizard'
    _description = 'Run Tests Wizard'

    name = fields.Char(string='Run Name', default=lambda self: self._default_name())
    suite_id = fields.Many2one('qa.test.suite', string='Test Suite')
    test_case_ids = fields.Many2many('qa.test.case', string='Test Cases')
    
    # Configuration
    config_id = fields.Many2one('qa.test.ai.config', string='Configuration',
                                default=lambda self: self.env['qa.test.ai.config'].search([], limit=1))
    
    # Environment
    environment = fields.Selection([
        ('local', 'Local'),
        ('staging', 'Staging'),
        ('production', 'Production'),
    ], string='Environment', default='local')
    base_url = fields.Char(string='Base URL', related='config_id.test_base_url', readonly=False)
    
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

    @api.onchange('suite_id')
    def _onchange_suite_id(self):
        if self.suite_id:
            self.test_case_ids = self.suite_id.test_case_ids
            self.include_tags = self.suite_id.include_tags
            self.exclude_tags = self.suite_id.exclude_tags

    def action_run(self):
        """Create and execute test run"""
        self.ensure_one()
        
        if not self.test_case_ids:
            raise UserError('Please select at least one test case.')
        
        if not self.config_id:
            raise UserError('Please configure test settings first.')
        
        # Filter test cases by tags if specified
        test_cases = self._filter_tests_by_tags()
        
        if not test_cases:
            raise UserError('No test cases match the tag filters.')
        
        # Create test run
        run = self.env['qa.test.run'].create({
            'name': self.name,
            'suite_id': self.suite_id.id if self.suite_id else False,
            'test_case_ids': [(6, 0, test_cases.ids)],
            'config_id': self.config_id.id,
            'environment': self.environment,
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
        """Select all available test cases"""
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
        failed_tests = self.env['qa.test.case'].search([('state', 'in', ['failed', 'error'])])
        self.test_case_ids = failed_tests
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
