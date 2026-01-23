# -*- coding: utf-8 -*-
"""
AI Import Mapping

Maps source columns to target Odoo fields.
"""

from odoo import models, fields, api


class AiImportMapping(models.Model):
    """Field mapping for import job."""
    _name = 'ai.import.mapping'
    _description = 'Import Field Mapping'
    _order = 'sequence, id'

    job_id = fields.Many2one('ai.import.job', string='Import Job',
        required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', default=10)
    
    # Source
    source_column = fields.Char('Source Column', required=True)
    sample_values = fields.Char('Sample Values', compute='_compute_sample_values')
    
    # Target
    target_field_id = fields.Many2one('ir.model.fields', string='Target Field',
        domain="[('model_id', '=', parent.target_model_id)]")
    target_field_name = fields.Char(related='target_field_id.name')
    target_field_type = fields.Selection(related='target_field_id.ttype')
    target_field_required = fields.Boolean(related='target_field_id.required')
    
    # Options
    transform = fields.Selection([
        ('none', 'None'),
        ('upper', 'UPPERCASE'),
        ('lower', 'lowercase'),
        ('title', 'Title Case'),
        ('strip', 'Strip Whitespace'),
    ], string='Transform', default='none')
    
    default_value = fields.Char('Default Value',
        help='Value to use if source is empty')
    
    # Mapping confidence (from auto-map)
    confidence = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
        ('manual', 'Manual'),
    ], string='Confidence', default='manual')
    
    skip = fields.Boolean('Skip', help='Do not import this column')

    @api.depends('job_id.preview_data', 'source_column')
    def _compute_sample_values(self):
        for rec in self:
            if not rec.job_id.preview_data or not rec.source_column:
                rec.sample_values = ''
                continue
            
            try:
                import json
                data = json.loads(rec.job_id.preview_data)
                samples = []
                for row in data[:5]:
                    val = row.get(rec.source_column)
                    if val:
                        samples.append(str(val)[:20])
                rec.sample_values = ', '.join(samples[:3])
            except Exception:
                rec.sample_values = ''

    @api.onchange('target_field_id')
    def _onchange_target_field(self):
        if self.target_field_id:
            self.confidence = 'manual'
