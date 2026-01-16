# -*- coding: utf-8 -*-
from odoo import models, fields, api
import hashlib

class AiErrorPattern(models.Model):
    _name = 'ai.error.pattern'
    _description = 'Error Pattern'
    _order = 'occurrences desc'

    odoo_version = fields.Selection([
        ('all', 'All'), ('17.0', '17.0'), ('18.0', '18.0'), ('19.0', '19.0'),
    ], required=True)
    task_type = fields.Selection([
        ('upgrade', 'Upgrade'), ('enhancement', 'Enhancement'),
        ('robot_test', 'Robot Test'), ('python_test', 'Python Test'),
        ('general', 'General'),
    ], required=True)
    error_type = fields.Selection([
        ('field_not_found', 'Field Not Found'), ('method_not_found', 'Method Not Found'),
        ('import_error', 'Import Error'), ('view_error', 'View Error'),
        ('locator_error', 'Locator Error'), ('other', 'Other'),
    ])
    error_signature = fields.Char('Signature', index=True)
    error_message = fields.Text('Error Message')
    model_name = fields.Char('Model')
    wrong_code = fields.Text('Wrong Code')
    correct_code = fields.Text('Correct Code')
    fix_explanation = fields.Text('Fix Explanation')
    occurrences = fields.Integer('Occurrences', default=1)
    resolved = fields.Boolean('Resolved', default=False)

    @api.model
    def record_error(self, version, task_type, error_text, wrong_code, model=None, agent=None):
        sig = hashlib.md5(f"{version}|{task_type}|{error_text[:100]}".encode()).hexdigest()[:16]
        existing = self.search([('error_signature', '=', sig)], limit=1)
        if existing:
            existing.occurrences += 1
            return existing
        return self.create({
            'odoo_version': version, 'task_type': task_type,
            'error_signature': sig, 'error_message': error_text[:1000],
            'model_name': model, 'wrong_code': wrong_code,
        })

    def record_fix(self, correct_code, explanation=None):
        self.write({'correct_code': correct_code, 'fix_explanation': explanation, 'resolved': True})
