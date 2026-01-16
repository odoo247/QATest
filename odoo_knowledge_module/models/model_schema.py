# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json

class AiModelSchema(models.Model):
    _name = 'ai.model.schema'
    _description = 'Model Schema'
    _order = 'model_name'

    model_name = fields.Char('Model', required=True, index=True)
    odoo_version = fields.Selection([
        ('17.0', '17.0'), ('18.0', '18.0'), ('19.0', '19.0'),
    ], required=True)
    fields_json = fields.Text('Fields (JSON)')
    description = fields.Char('Description')
    field_count = fields.Integer(compute='_compute_field_count')

    @api.depends('fields_json')
    def _compute_field_count(self):
        for r in self:
            r.field_count = len(json.loads(r.fields_json or '{}'))

    @api.model
    def extract_from_odoo(self, model_name, version=None):
        Model = self.env[model_name]
        fields_info = {k: {'type': v.get('type'), 'string': v.get('string')} 
                       for k, v in Model.fields_get().items()}
        version = version or '19.0'
        existing = self.search([('model_name', '=', model_name), ('odoo_version', '=', version)], limit=1)
        vals = {'model_name': model_name, 'odoo_version': version, 'fields_json': json.dumps(fields_info)}
        return existing.write(vals) and existing or self.create(vals)
