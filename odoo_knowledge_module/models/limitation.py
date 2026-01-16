# -*- coding: utf-8 -*-
from odoo import models, fields

class AiLimitation(models.Model):
    _name = 'ai.limitation'
    _description = 'Known Limitation'

    area = fields.Selection([
        ('sales', 'Sales'), ('purchase', 'Purchase'), ('inventory', 'Inventory'),
        ('manufacturing', 'Manufacturing'), ('accounting', 'Accounting'),
        ('hr', 'HR'), ('pos', 'POS'), ('general', 'General'),
    ], required=True)
    limitation = fields.Char('Limitation', required=True)
    description = fields.Text('Description')
    workaround = fields.Text('Workaround')
    workaround_complexity = fields.Selection([
        ('simple', 'Simple'), ('moderate', 'Moderate'), ('complex', 'Complex'),
        ('not_possible', 'Not Possible'),
    ])
    keywords = fields.Char('Keywords')
    active = fields.Boolean(default=True)

    def to_context(self):
        self.ensure_one()
        r = f"❌ {self.area}: {self.limitation}"
        if self.workaround:
            r += f"\n  Workaround: {self.workaround}"
        return r
