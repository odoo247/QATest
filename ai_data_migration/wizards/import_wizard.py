import base64
import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MigrationImportWizard(models.TransientModel):
    _name = 'migration.import.wizard'
    _description = 'Quick Import Wizard'

    # Source file
    source_file = fields.Binary(
        string='Source File',
        required=True,
    )
    source_filename = fields.Char(string='Filename')
    
    source_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File'),
        ('json', 'JSON File'),
    ], string='File Type', compute='_compute_source_type', store=True)
    
    # Target
    target_model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        required=True,
        domain=[('transient', '=', False)],
    )
    
    # Template
    use_template = fields.Boolean(string='Use Template')
    template_id = fields.Many2one(
        'migration.template',
        string='Template',
        domain="[('target_model_id', '=', target_model_id)]",
    )
    
    # Options
    use_ai_mapping = fields.Boolean(
        string='Use AI Mapping',
        default=True,
        help='Use AI to automatically suggest field mappings',
    )
    
    @api.depends('source_filename')
    def _compute_source_type(self):
        for record in self:
            if record.source_filename:
                filename = record.source_filename.lower()
                if filename.endswith('.csv'):
                    record.source_type = 'csv'
                elif filename.endswith(('.xlsx', '.xls')):
                    record.source_type = 'excel'
                elif filename.endswith('.json'):
                    record.source_type = 'json'
                else:
                    record.source_type = 'csv'  # Default
            else:
                record.source_type = 'csv'
    
    def action_create_project(self):
        """Create a migration project from the wizard."""
        self.ensure_one()
        
        # Create project
        project = self.env['migration.project'].create({
            'name': f'Import {self.source_filename or "Data"} to {self.target_model_id.name}',
            'source_type': self.source_type,
            'source_file': self.source_file,
            'source_filename': self.source_filename,
            'target_model_id': self.target_model_id.id,
        })
        
        # Parse the source file
        project._parse_source_file()
        
        # Apply template if selected
        if self.use_template and self.template_id:
            self.template_id.apply_to_project(project)
            project.state = 'mapping'
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'migration.project',
                'res_id': project.id,
                'view_mode': 'form',
            }
        
        # Use AI mapping if selected
        if self.use_ai_mapping:
            return {
                'name': _('AI Field Mapping'),
                'type': 'ir.actions.act_window',
                'res_model': 'migration.ai.mapping.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_project_id': project.id,
                },
            }
        
        # Otherwise, open project for manual mapping
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'migration.project',
            'res_id': project.id,
            'view_mode': 'form',
        }


class MigrationValueMappingWizard(models.TransientModel):
    _name = 'migration.value.mapping.wizard'
    _description = 'Value Mapping Editor'

    mapping_id = fields.Many2one(
        'migration.mapping',
        string='Field Mapping',
        required=True,
    )
    
    current_mapping = fields.Text(
        string='Current Mapping',
        help='JSON format: {"source_value": "target_value", ...}',
    )
    
    line_ids = fields.One2many(
        'migration.value.mapping.wizard.line',
        'wizard_id',
        string='Value Mappings',
    )
    
    @api.onchange('current_mapping')
    def _onchange_current_mapping(self):
        """Parse current mapping and create lines."""
        if self.current_mapping:
            try:
                mapping = json.loads(self.current_mapping)
                self.line_ids = [(5, 0, 0)]  # Clear
                for source, target in mapping.items():
                    self.line_ids = [(0, 0, {
                        'source_value': source,
                        'target_value': target,
                    })]
            except json.JSONDecodeError:
                pass
    
    def action_save(self):
        """Save the value mapping."""
        self.ensure_one()
        
        mapping = {}
        for line in self.line_ids:
            if line.source_value:
                mapping[line.source_value] = line.target_value or ''
        
        self.mapping_id.value_mapping = json.dumps(mapping)
        
        return {'type': 'ir.actions.act_window_close'}
    
    def action_detect_values(self):
        """Detect unique values from sample data."""
        self.ensure_one()
        
        project = self.mapping_id.project_id
        if not project.preview_data:
            return
        
        preview = json.loads(project.preview_data)
        source_col = self.mapping_id.source_column
        
        unique_values = set()
        for row in preview:
            val = row.get(source_col, '')
            if val:
                unique_values.add(str(val))
        
        # Clear and recreate lines
        self.line_ids.unlink()
        for val in sorted(unique_values):
            self.env['migration.value.mapping.wizard.line'].create({
                'wizard_id': self.id,
                'source_value': val,
                'target_value': '',
            })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class MigrationValueMappingWizardLine(models.TransientModel):
    _name = 'migration.value.mapping.wizard.line'
    _description = 'Value Mapping Line'

    wizard_id = fields.Many2one(
        'migration.value.mapping.wizard',
        string='Wizard',
        ondelete='cascade',
    )
    
    source_value = fields.Char(string='Source Value')
    target_value = fields.Char(string='Target Value')
