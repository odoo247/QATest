# -*- coding: utf-8 -*-
from odoo import models, fields

class AiConfigOption(models.Model):
    _name = 'ai.config.option'
    _description = 'Configuration Option'

    name = fields.Char('Name', required=True)
    module = fields.Char('Module')
    config_type = fields.Selection([
        ('setting', 'Setting'), ('studio', 'Studio'), ('ui', 'UI'), ('data', 'Data'),
    ], default='setting')
    description = fields.Text('Description')
    location = fields.Char('Location')
    steps = fields.Text('Steps')
    requires_studio = fields.Boolean('Requires Studio')
    requires_enterprise = fields.Boolean('Requires Enterprise')
    complexity = fields.Selection([
        ('trivial', 'Trivial'), ('simple', 'Simple'), ('moderate', 'Moderate'),
    ], default='simple')
    estimated_hours = fields.Float('Hours', default=1.0)
    keywords = fields.Char('Keywords')
    active = fields.Boolean(default=True)

    def to_context(self):
        self.ensure_one()
        return f"### Config: {self.name}\nEffort: ~{self.estimated_hours}h\n{self.description or ''}"
