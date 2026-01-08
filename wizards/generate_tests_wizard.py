# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class QATestGenerateWizard(models.TransientModel):
    _name = 'qa.test.generate.wizard'
    _description = 'Generate Tests Wizard'

    spec_ids = fields.Many2many('qa.test.spec', string='Specifications')
    
    # Options
    analyze_first = fields.Boolean(string='Analyze Modules First', default=True,
                                   help='Analyze Odoo modules before generating tests')
    regenerate_existing = fields.Boolean(string='Regenerate Existing', default=False,
                                         help='Delete and regenerate existing test cases')
    
    # AI Options
    config_id = fields.Many2one('qa.test.ai.config', string='AI Configuration',
                                default=lambda self: self.env['qa.test.ai.config'].search([], limit=1))
    include_negative_tests = fields.Boolean(string='Include Negative Tests', default=True,
                                            help='Generate tests for error scenarios')
    include_edge_cases = fields.Boolean(string='Include Edge Cases', default=True,
                                        help='Generate tests for boundary conditions')
    test_depth = fields.Selection([
        ('basic', 'Basic - Core functionality only'),
        ('standard', 'Standard - Normal test coverage'),
        ('comprehensive', 'Comprehensive - Full coverage'),
    ], string='Test Depth', default='standard')
    
    # Progress
    state = fields.Selection([
        ('draft', 'Ready'),
        ('analyzing', 'Analyzing Modules...'),
        ('generating', 'Generating Tests...'),
        ('done', 'Complete'),
        ('error', 'Error'),
    ], string='State', default='draft')
    progress_message = fields.Char(string='Progress')
    error_message = fields.Text(string='Error')
    
    # Results
    generated_count = fields.Integer(string='Tests Generated', readonly=True)
    
    def action_generate(self):
        """Generate tests for selected specifications"""
        self.ensure_one()
        
        if not self.spec_ids:
            raise UserError('Please select at least one specification.')
        
        if not self.config_id:
            raise UserError('Please configure AI settings first.')
        
        self.state = 'analyzing'
        self.progress_message = 'Starting...'
        
        total_generated = 0
        errors = []
        
        for spec in self.spec_ids:
            try:
                # Analyze module if requested
                if self.analyze_first and spec.module_id:
                    self.progress_message = f'Analyzing module: {spec.module_id.name}'
                    spec.action_analyze_module()
                
                # Delete existing tests if regenerating
                if self.regenerate_existing:
                    spec.test_case_ids.unlink()
                
                # Generate tests
                self.state = 'generating'
                self.progress_message = f'Generating tests for: {spec.name}'
                spec._generate_tests()
                
                total_generated += spec.test_case_count
                
            except Exception as e:
                _logger.error(f"Generation failed for {spec.name}: {str(e)}")
                errors.append(f"{spec.name}: {str(e)}")
        
        self.generated_count = total_generated
        
        if errors:
            self.state = 'error'
            self.error_message = '\n'.join(errors)
        else:
            self.state = 'done'
            self.progress_message = f'Generated {total_generated} test cases'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_view_generated(self):
        """View generated test cases"""
        return {
            'name': 'Generated Tests',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.case',
            'view_mode': 'tree,form',
            'domain': [('spec_id', 'in', self.spec_ids.ids)],
        }
    
    def action_close(self):
        """Close wizard"""
        return {'type': 'ir.actions.act_window_close'}
