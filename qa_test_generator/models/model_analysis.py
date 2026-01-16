# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json


class QAModelAnalysis(models.Model):
    _name = 'qa.model.analysis'
    _description = 'Model Analysis'
    _order = 'model_name'

    module_id = fields.Many2one('qa.scanned.module', string='Module',
                                 required=True, ondelete='cascade')
    model_name = fields.Char(string='Model Name', required=True)
    model_description = fields.Char(string='Description')
    inherit_model = fields.Char(string='Inherits')
    
    field_count = fields.Integer(string='Fields')
    method_count = fields.Integer(string='Methods')
    has_workflow = fields.Boolean(string='Has Workflow')
    has_constraints = fields.Boolean(string='Has Constraints')
    
    analysis_json = fields.Text(string='Full Analysis (JSON)')
    suggested_tests = fields.Text(string='Suggested Tests', compute='_compute_suggested_tests')
    test_count = fields.Integer(string='Generated Tests')
    
    # Related
    customer_id = fields.Many2one(related='module_id.customer_id', store=True)
    scan_id = fields.Many2one(related='module_id.scan_id', store=True)

    @api.depends('analysis_json')
    def _compute_suggested_tests(self):
        for record in self:
            if record.analysis_json:
                try:
                    data = json.loads(record.analysis_json)
                    tests = []
                    
                    # CRUD tests
                    tests.append(f"• CRUD: Create/Read/Update/Delete {record.model_name}")
                    
                    # Field validation tests
                    required = [f['name'] for f in data.get('fields', []) if f.get('required')]
                    if required:
                        tests.append(f"• Validation: Required fields ({', '.join(required[:3])}...)")
                    
                    # Workflow tests
                    if data.get('has_workflow'):
                        states = data.get('states', [])
                        if states:
                            tests.append(f"• Workflow: State transitions ({' → '.join(states[:4])})")
                    
                    # Constraint tests
                    constraints = data.get('constraints', [])
                    for c in constraints[:2]:
                        tests.append(f"• Constraint: {c.get('name', 'Unknown')}")
                    
                    # Method tests
                    actions = [m['name'] for m in data.get('methods', []) if m.get('is_action')]
                    for a in actions[:3]:
                        tests.append(f"• Action: {a}()")
                    
                    record.suggested_tests = '\n'.join(tests)
                except:
                    record.suggested_tests = "Unable to parse analysis"
            else:
                record.suggested_tests = ""

    def action_view_full_analysis(self):
        """View full JSON analysis"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Analysis - {self.model_name}',
            'res_model': 'qa.model.analysis',
            'res_id': self.id,
            'view_mode': 'form',
        }
