# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class QAModuleAnalysis(models.Model):
    _name = 'qa.module.analysis'
    _description = 'Module Analysis Cache'
    _order = 'analysis_date desc'

    name = fields.Char(string='Analysis Name', compute='_compute_name', store=True)
    module_id = fields.Many2one('ir.module.module', string='Module', required=True,
                                 ondelete='cascade')
    module_name = fields.Char(string='Technical Name', related='module_id.name', store=True)
    
    # Analysis date
    analysis_date = fields.Datetime(string='Analysis Date', default=fields.Datetime.now)
    
    # Analysis results
    models_data = fields.Text(string='Models Data (JSON)')
    views_data = fields.Text(string='Views Data (JSON)')
    fields_data = fields.Text(string='Fields Data (JSON)')
    buttons_data = fields.Text(string='Buttons Data (JSON)')
    menus_data = fields.Text(string='Menus Data (JSON)')
    
    # Summary
    model_count = fields.Integer(string='Models Count')
    view_count = fields.Integer(string='Views Count')
    field_count = fields.Integer(string='Fields Count')
    button_count = fields.Integer(string='Buttons Count')
    
    # Human-readable summaries
    models_summary = fields.Text(string='Models Summary')
    views_summary = fields.Text(string='Views Summary')
    fields_summary = fields.Text(string='Fields Summary')
    buttons_summary = fields.Text(string='Buttons Summary')
    
    # Analysis status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('analyzing', 'Analyzing'),
        ('complete', 'Complete'),
        ('error', 'Error'),
    ], string='Status', default='draft')
    error_message = fields.Text(string='Error Message')

    @api.depends('module_id', 'analysis_date')
    def _compute_name(self):
        for record in self:
            if record.module_id and record.analysis_date:
                date_str = record.analysis_date.strftime('%Y-%m-%d %H:%M')
                record.name = f"{record.module_id.name} - {date_str}"
            else:
                record.name = 'New Analysis'

    def action_analyze(self):
        """Run analysis on the module"""
        self.ensure_one()
        self.state = 'analyzing'
        
        try:
            from ..services.code_analyzer import CodeAnalyzer
            analyzer = CodeAnalyzer(self.env)
            result = analyzer.analyze_module_full(self.module_name)
            
            import json
            self.write({
                'models_data': json.dumps(result.get('models_raw', {})),
                'views_data': json.dumps(result.get('views_raw', {})),
                'fields_data': json.dumps(result.get('fields_raw', {})),
                'buttons_data': json.dumps(result.get('buttons_raw', {})),
                'menus_data': json.dumps(result.get('menus_raw', {})),
                'models_summary': result.get('models_summary', ''),
                'views_summary': result.get('views_summary', ''),
                'fields_summary': result.get('fields_summary', ''),
                'buttons_summary': result.get('buttons_summary', ''),
                'model_count': result.get('model_count', 0),
                'view_count': result.get('view_count', 0),
                'field_count': result.get('field_count', 0),
                'button_count': result.get('button_count', 0),
                'state': 'complete',
            })
            
        except Exception as e:
            _logger.error(f"Module analysis failed: {str(e)}")
            self.write({
                'state': 'error',
                'error_message': str(e),
            })
            raise

    @api.model
    def get_or_create_analysis(self, module_name):
        """Get existing analysis or create new one"""
        module = self.env['ir.module.module'].search([('name', '=', module_name)], limit=1)
        if not module:
            return False
        
        # Check for recent analysis (within 24 hours)
        from datetime import datetime, timedelta
        recent = self.search([
            ('module_id', '=', module.id),
            ('state', '=', 'complete'),
            ('analysis_date', '>=', datetime.now() - timedelta(hours=24)),
        ], limit=1, order='analysis_date desc')
        
        if recent:
            return recent
        
        # Create new analysis
        analysis = self.create({
            'module_id': module.id,
        })
        analysis.action_analyze()
        return analysis
