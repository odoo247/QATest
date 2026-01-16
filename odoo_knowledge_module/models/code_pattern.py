# -*- coding: utf-8 -*-
from odoo import models, fields

class AiCodePattern(models.Model):
    _name = 'ai.code.pattern'
    _description = 'Code Pattern'
    _order = 'name'

    name = fields.Char('Name', required=True)
    category = fields.Selection([
        ('model', 'Model'), ('field', 'Field'), ('method', 'Method'),
        ('view', 'View'), ('controller', 'Controller'), ('wizard', 'Wizard'),
        ('report', 'Report'), ('security', 'Security'), ('js', 'JavaScript'),
    ], required=True)
    odoo_version = fields.Selection([
        ('all', 'All'), ('17.0', '17.0'), ('18.0', '18.0'), ('19.0', '19.0'),
    ], default='all')
    description = fields.Text('Description')
    code_template = fields.Text('Code Template', required=True)
    usage_example = fields.Text('Usage Example')
    variables = fields.Char('Variables')
    tags = fields.Char('Tags')
    active = fields.Boolean(default=True)

    def to_context(self):
        self.ensure_one()
        return f"### {self.name}\n```python\n{self.code_template}\n```"
