# -*- coding: utf-8 -*-

from odoo import models, fields, api


class QAScannedModule(models.Model):
    _name = 'qa.scanned.module'
    _description = 'Scanned Odoo Module'
    _order = 'technical_name'

    scan_id = fields.Many2one('qa.code.scan', string='Scan', 
                               required=True, ondelete='cascade')
    technical_name = fields.Char(string='Technical Name', required=True)
    display_name = fields.Char(string='Display Name')
    version = fields.Char(string='Version')
    path = fields.Char(string='Path in Repository')
    depends = fields.Char(string='Dependencies')
    
    model_count = fields.Integer(string='Models')
    view_count = fields.Integer(string='Views')
    
    selected = fields.Boolean(string='Selected', default=True)
    
    state = fields.Selection([
        ('discovered', 'Discovered'),
        ('analyzed', 'Analyzed'),
        ('generated', 'Tests Generated'),
    ], string='Status', default='discovered')
    
    analysis_ids = fields.One2many('qa.model.analysis', 'module_id', string='Model Analyses')
    analysis_count = fields.Integer(compute='_compute_analysis_count')
    
    # Link to generated suite
    suite_id = fields.Many2one('qa.test.suite', string='Test Suite', 
                                ondelete='set null',
                                help='Generated test suite for this module')
    test_count = fields.Integer(related='suite_id.test_case_count', string='Tests')
    
    # Related
    customer_id = fields.Many2one(related='scan_id.customer_id', store=True)

    @api.depends('analysis_ids')
    def _compute_analysis_count(self):
        for record in self:
            record.analysis_count = len(record.analysis_ids)

    def action_view_analysis(self):
        """View model analyses"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Analysis - {self.technical_name}',
            'res_model': 'qa.model.analysis',
            'view_mode': 'list,form',
            'domain': [('module_id', '=', self.id)],
        }

    def action_view_suite(self):
        """View generated test suite"""
        self.ensure_one()
        if not self.suite_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': f'Test Suite - {self.technical_name}',
            'res_model': 'qa.test.suite',
            'view_mode': 'form',
            'res_id': self.suite_id.id,
        }

    def action_reset_module(self):
        """Reset module to analyzed state to allow regenerating tests"""
        for record in self:
            if record.state == 'generated':
                # Delete existing test cases for this module
                test_cases = self.env['qa.test.case'].search([
                    ('suite_id', '=', record.suite_id.id)
                ])
                test_cases.unlink()
                
                # Delete the suite
                if record.suite_id:
                    record.suite_id.unlink()
                
                # Reset analysis test counts
                record.analysis_ids.write({'test_count': 0})
                
                record.state = 'analyzed'
                
                # Update scan state if needed
                if record.scan_id.state == 'done':
                    record.scan_id.state = 'analyzed'

    def action_reset_to_discovered(self):
        """Reset module to discovered state to allow re-analyzing"""
        for record in self:
            # Delete test cases and suite
            if record.suite_id:
                test_cases = self.env['qa.test.case'].search([
                    ('suite_id', '=', record.suite_id.id)
                ])
                test_cases.unlink()
                record.suite_id.unlink()
            
            # Delete analyses
            record.analysis_ids.unlink()
            
            record.state = 'discovered'
            
            # Update scan state if needed
            if record.scan_id.state in ('analyzed', 'done'):
                record.scan_id.state = 'scanned'
