# -*- coding: utf-8 -*-
from odoo import models, fields

class AiModuleFeature(models.Model):
    _name = 'ai.module.feature'
    _description = 'Standard Module Feature'

    module = fields.Char('Module', required=True, index=True)
    module_category = fields.Selection([
        ('sales', 'Sales'), ('purchase', 'Purchase'), ('inventory', 'Inventory'),
        ('manufacturing', 'Manufacturing'), ('accounting', 'Accounting'),
        ('crm', 'CRM'), ('hr', 'HR'), ('project', 'Project'), ('other', 'Other'),
    ])
    name = fields.Char('Feature Name', required=True)
    description = fields.Text('Description')
    capabilities = fields.Text('Capabilities')
    limitations = fields.Text('Limitations')
    edition = fields.Selection([('community', 'Community'), ('enterprise', 'Enterprise')], default='community')
    keywords = fields.Char('Keywords')
    active = fields.Boolean(default=True)

    def to_context(self):
        self.ensure_one()
        return f"### {self.name} ({self.module})\n{self.description or ''}"
