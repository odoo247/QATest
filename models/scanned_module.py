# -*- coding: utf-8 -*-

from odoo import models, fields, api


class QAScannedModule(models.Model):
    _name = 'qa.scanned.module'
    _description = 'Scanned Odoo Module'
    _order = 'technical_name'

    scan_id = fields.Many2one('qa.code.scan', string='Scan', 
                               required=True, ondelete='cascade')
    technical_name = fields.Char(string='Technical Name', required=True)
    display_name = fields.Char(string='Display Name')
    version = fields.Char(string='Version')
    path = fields.Char(string='Path in Repository')
    depends = fields.Char(string='Dependencies')
    
    model_count = fields.Integer(string='Models')
    view_count = fields.Integer(string='Views')
    
    selected = fields.Boolean(string='Selected', default=True)
    
    state = fields.Selection([
        ('discovered', 'Discovered'),
        ('analyzed', 'Analyzed'),
        ('generated', 'Tests Generated'),
    ], string='Status', default='discovered')
    
    analysis_ids = fields.One2many('qa.model.analysis', 'module_id', string='Model Analyses')
    analysis_count = fields.Integer(compute='_compute_analysis_count')
    
    # Related
    customer_id = fields.Many2one(related='scan_id.customer_id', store=True)

    @api.depends('analysis_ids')
    def _compute_analysis_count(self):
        for record in self:
            record.analysis_count = len(record.analysis_ids)

    def action_view_analysis(self):
        """View model analyses"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Analysis - {self.technical_name}',
            'res_model': 'qa.model.analysis',
            'view_mode': 'list,form',
            'domain': [('module_id', '=', self.id)],
        }
