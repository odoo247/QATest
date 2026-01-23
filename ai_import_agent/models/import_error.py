# -*- coding: utf-8 -*-
"""
AI Import Error

Tracks errors during import with KB integration.
"""

from odoo import models, fields, api


class AiImportError(models.Model):
    """Error record for import job."""
    _name = 'ai.import.error'
    _description = 'Import Error'
    _order = 'row_number'

    job_id = fields.Many2one('ai.import.job', string='Import Job',
        required=True, ondelete='cascade')
    
    # Error location
    row_number = fields.Integer('Row #')
    field_name = fields.Char('Field')
    
    # Error details
    error_type = fields.Selection([
        ('validation', 'Validation'),
        ('import', 'Import'),
        ('transform', 'Transform'),
    ], string='Type', default='import')
    
    error_message = fields.Text('Error Message')
    source_value = fields.Char('Source Value')
    source_data = fields.Text('Source Row (JSON)')
    
    # KB integration
    kb_suggestion = fields.Text('KB Suggestion',
        help='Suggested fix from Knowledge Base')
    kb_error_id = fields.Many2one('ai.error.pattern', string='KB Error Pattern')
    
    # Resolution
    resolved = fields.Boolean('Resolved')
    resolution_notes = fields.Text('Resolution Notes')

    def action_lookup_kb(self):
        """Look up this error in KB."""
        self.ensure_one()
        
        if not self.error_message:
            return
        
        try:
            patterns = self.job_id.kb_get_error_patterns(self.error_message, 'general')
            if patterns:
                self.kb_suggestion = patterns[0].get('fix') or patterns[0].get('explanation')
        except Exception:
            pass

    def action_record_to_kb(self):
        """Record this error to KB for future learning."""
        self.ensure_one()
        
        if not self.error_message:
            return
        
        error = self.job_id.kb_record_error(
            odoo_version='18.0',
            task_type='general',
            error_text=self.error_message,
            wrong_code=self.source_data or self.source_value or '',
        )
        
        if error:
            self.kb_error_id = error.id
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Error Recorded',
                'message': 'Error pattern saved to Knowledge Base',
                'type': 'success',
            }
        }

    def action_record_fix(self):
        """Record a fix for this error to KB."""
        self.ensure_one()
        
        if not self.kb_error_id and not self.error_message:
            return
        
        # If no KB error exists, create one first
        if not self.kb_error_id:
            self.action_record_to_kb()
        
        if self.kb_error_id and self.resolution_notes:
            self.job_id.kb_record_fix(
                error_id=self.kb_error_id.id,
                correct_code=self.resolution_notes,
                explanation=f'Fix for import error: {self.error_message[:100]}',
            )
            self.resolved = True
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Fix Recorded',
                'message': 'Fix saved to Knowledge Base',
                'type': 'success',
            }
        }
