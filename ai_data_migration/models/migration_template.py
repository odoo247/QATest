import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MigrationTemplate(models.Model):
    _name = 'migration.template'
    _description = 'Migration Template'
    _order = 'name'

    name = fields.Char(string='Template Name', required=True)
    description = fields.Text(string='Description')
    
    # Target model
    target_model_id = fields.Many2one(
        'ir.model',
        string='Target Model',
        required=True,
    )
    target_model_name = fields.Char(
        related='target_model_id.model',
        store=True,
    )
    
    # Source configuration
    source_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File'),
        ('json', 'JSON File'),
    ], string='Source Type', default='csv')
    
    csv_delimiter = fields.Char(string='CSV Delimiter', default=',')
    csv_encoding = fields.Selection([
        ('utf-8', 'UTF-8'),
        ('latin-1', 'Latin-1'),
        ('cp1252', 'Windows-1252'),
    ], string='File Encoding', default='utf-8')
    has_header = fields.Boolean(string='Has Header Row', default=True)
    
    # Import settings
    batch_size = fields.Integer(string='Batch Size', default=100)
    on_error = fields.Selection([
        ('stop', 'Stop Import'),
        ('skip', 'Skip Record'),
        ('log', 'Log and Continue'),
    ], string='On Error', default='skip')
    
    create_if_not_exists = fields.Boolean(string='Create Related Records')
    update_existing = fields.Boolean(string='Update Existing Records')
    unique_field_id = fields.Many2one(
        'ir.model.fields',
        string='Unique Identifier Field',
    )
    
    # Mappings stored as JSON
    mappings_json = fields.Text(
        string='Mappings Configuration',
        help='JSON configuration of field mappings',
    )
    
    # Usage tracking
    use_count = fields.Integer(string='Times Used', readonly=True, default=0)
    last_used = fields.Datetime(string='Last Used', readonly=True)
    
    # Sharing
    is_shared = fields.Boolean(
        string='Shared Template',
        default=False,
        help='Allow other users to use this template',
    )
    
    # Tags for organization
    tag_ids = fields.Many2many(
        'migration.template.tag',
        string='Tags',
    )
    
    @api.model
    def create_from_project(self, project, name, description=''):
        """Create a template from an existing project configuration."""
        mappings = []
        for mapping in project.mapping_ids:
            mapping_data = {
                'source_column': mapping.source_column,
                'target_field_name': mapping.target_field_id.name if mapping.target_field_id else None,
                'mapping_type': mapping.mapping_type,
                'default_value': mapping.default_value,
                'date_format': mapping.date_format,
                'relation_search_field': mapping.relation_search_field,
                'multi_value_delimiter': mapping.multi_value_delimiter,
                'value_mapping': mapping.value_mapping,
                'transformation_ids': mapping.transformation_ids.mapped('name'),
            }
            mappings.append(mapping_data)
        
        return self.create({
            'name': name,
            'description': description,
            'target_model_id': project.target_model_id.id,
            'source_type': project.source_type,
            'csv_delimiter': project.csv_delimiter,
            'csv_encoding': project.csv_encoding,
            'has_header': project.has_header,
            'batch_size': project.batch_size,
            'on_error': project.on_error,
            'create_if_not_exists': project.create_if_not_exists,
            'update_existing': project.update_existing,
            'unique_field_id': project.unique_field_id.id if project.unique_field_id else False,
            'mappings_json': json.dumps(mappings, indent=2),
        })
    
    def apply_to_project(self, project):
        """Apply template configuration to a project."""
        self.ensure_one()
        
        # Update project settings
        project.write({
            'target_model_id': self.target_model_id.id,
            'source_type': self.source_type,
            'csv_delimiter': self.csv_delimiter,
            'csv_encoding': self.csv_encoding,
            'has_header': self.has_header,
            'batch_size': self.batch_size,
            'on_error': self.on_error,
            'create_if_not_exists': self.create_if_not_exists,
            'update_existing': self.update_existing,
            'unique_field_id': self.unique_field_id.id if self.unique_field_id else False,
        })
        
        # Clear existing mappings
        project.mapping_ids.unlink()
        
        # Create mappings from template
        if self.mappings_json:
            mappings_data = json.loads(self.mappings_json)
            source_columns = json.loads(project.source_columns) if project.source_columns else []
            
            MappingModel = self.env['migration.mapping']
            TransformRule = self.env['migration.transformation.rule']
            
            for mapping_data in mappings_data:
                # Skip if source column not in project's file
                if mapping_data['source_column'] not in source_columns:
                    continue
                
                # Find target field
                target_field = None
                if mapping_data.get('target_field_name'):
                    target_field = self.env['ir.model.fields'].search([
                        ('model_id', '=', project.target_model_id.id),
                        ('name', '=', mapping_data['target_field_name']),
                    ], limit=1)
                
                # Find transformation rules
                transform_ids = []
                if mapping_data.get('transformation_ids'):
                    transforms = TransformRule.search([
                        ('name', 'in', mapping_data['transformation_ids'])
                    ])
                    transform_ids = transforms.ids
                
                MappingModel.create({
                    'project_id': project.id,
                    'source_column': mapping_data['source_column'],
                    'target_field_id': target_field.id if target_field else False,
                    'mapping_type': mapping_data.get('mapping_type', 'direct'),
                    'default_value': mapping_data.get('default_value'),
                    'date_format': mapping_data.get('date_format'),
                    'relation_search_field': mapping_data.get('relation_search_field'),
                    'multi_value_delimiter': mapping_data.get('multi_value_delimiter'),
                    'value_mapping': mapping_data.get('value_mapping'),
                    'transformation_ids': [(6, 0, transform_ids)],
                })
        
        # Update usage stats
        self.write({
            'use_count': self.use_count + 1,
            'last_used': fields.Datetime.now(),
        })
        
        return True
    
    def action_duplicate(self):
        """Duplicate template."""
        self.ensure_one()
        new_template = self.copy({
            'name': f"{self.name} (Copy)",
            'use_count': 0,
            'last_used': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'migration.template',
            'res_id': new_template.id,
            'view_mode': 'form',
        }
    
    def action_view_mappings(self):
        """View template mappings in a readable format."""
        self.ensure_one()
        
        return {
            'name': _('Template Mappings'),
            'type': 'ir.actions.act_window',
            'res_model': 'migration.template.mappings.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
                'default_mappings_display': self.mappings_json,
            },
        }


class MigrationTemplateTag(models.Model):
    _name = 'migration.template.tag'
    _description = 'Migration Template Tag'

    name = fields.Char(string='Tag Name', required=True)
    color = fields.Integer(string='Color Index')
