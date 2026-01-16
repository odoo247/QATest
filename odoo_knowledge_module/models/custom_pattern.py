# -*- coding: utf-8 -*-
from odoo import models, fields

class AiCustomPattern(models.Model):
    _name = 'ai.custom.pattern'
    _description = 'Customisation Pattern'

    name = fields.Char('Name', required=True)
    pattern_type = fields.Selection([
        ('field', 'Field'), ('workflow', 'Workflow'), ('report', 'Report'),
        ('integration', 'Integration'), ('automation', 'Automation'), ('ui', 'UI'),
    ], required=True)
    description = fields.Text('Description')
    when_needed = fields.Text('When Needed')
    technical_approach = fields.Text('Technical Approach')
    code_example = fields.Text('Code Example')
    complexity = fields.Selection([
        ('simple', 'Simple'), ('moderate', 'Moderate'), ('complex', 'Complex'),
    ], default='moderate')
    estimated_days = fields.Float('Days', default=2.0)
    risks = fields.Text('Risks')
    keywords = fields.Char('Keywords')
    active = fields.Boolean(default=True)

    def to_context(self):
        self.ensure_one()
        return f"### Custom: {self.name}\nEffort: ~{self.estimated_days} days\n{self.description or ''}"
