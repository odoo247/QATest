# -*- coding: utf-8 -*-
from odoo import models, fields
import json, base64

class AiImportWizard(models.TransientModel):
    _name = 'ai.import.wizard'
    _description = 'Import Knowledge'

    file_data = fields.Binary('File', required=True)
    file_name = fields.Char('Filename')
    result = fields.Text('Result', readonly=True)

    def action_import(self):
        data = json.loads(base64.b64decode(self.file_data).decode('utf-8'))
        counts = {}
        
        for item in data.get('breaking_changes', []):
            try:
                self.env['ai.breaking.change'].create(item)
                counts['breaking_changes'] = counts.get('breaking_changes', 0) + 1
            except: pass
        
        for item in data.get('features', []):
            try:
                self.env['ai.module.feature'].create(item)
                counts['features'] = counts.get('features', 0) + 1
            except: pass
        
        for item in data.get('configurations', []):
            try:
                self.env['ai.config.option'].create(item)
                counts['configurations'] = counts.get('configurations', 0) + 1
            except: pass
        
        self.result = f"Imported: {counts}"
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}
