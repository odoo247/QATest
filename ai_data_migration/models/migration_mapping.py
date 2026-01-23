import json
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class MigrationMapping(models.Model):
    _name = 'migration.mapping'
    _description = 'Data Migration Field Mapping'
    _order = 'sequence, id'

    project_id = fields.Many2one(
        'migration.project',
        string='Migration Project',
        required=True,
        ondelete='cascade',
    )
    
    sequence = fields.Integer(string='Sequence', default=10)
    
    # Source Configuration
    source_column = fields.Char(
        string='Source Column',
        required=True,
    )
    source_sample_values = fields.Text(
        string='Sample Values',
        help='Sample values from the source data for this column',
    )
    
    # Target Configuration
    target_field_id = fields.Many2one(
        'ir.model.fields',
        string='Target Field',
        domain="[('model_id', '=', parent.target_model_id)]",
    )
    target_field_name = fields.Char(
        related='target_field_id.name',
        string='Field Name',
    )
    target_field_type = fields.Selection(
        related='target_field_id.ttype',
        string='Field Type',
    )
    target_field_required = fields.Boolean(
        related='target_field_id.required',
        string='Required',
    )
    target_field_relation = fields.Char(
        related='target_field_id.relation',
        string='Related Model',
    )
    
    # Mapping Configuration
    is_mapped = fields.Boolean(
        string='Is Mapped',
        compute='_compute_is_mapped',
        store=True,
    )
    
    mapping_type = fields.Selection([
        ('direct', 'Direct Mapping'),
        ('transform', 'With Transformation'),
        ('default', 'Default Value Only'),
        ('skip', 'Skip Column'),
    ], string='Mapping Type', default='direct')
    
    default_value = fields.Char(
        string='Default Value',
        help='Value to use when source is empty',
    )
    
    # Transformation Rules
    transformation_ids = fields.Many2many(
        'migration.transformation.rule',
        'migration_mapping_transformation_rel',
        'mapping_id',
        'transformation_id',
        string='Transformations',
    )
    
    # Date/Time handling
    date_format = fields.Char(
        string='Date Format',
        help='Python strftime format for date parsing (e.g., %Y-%m-%d)',
    )
    
    # Relational field handling
    relation_search_field = fields.Char(
        string='Search Field',
        default='name',
        help='Field to search in related model (default: name)',
    )
    relation_create_if_missing = fields.Boolean(
        string='Create if Missing',
        help='Create related record if not found',
    )
    
    # Multi-value handling
    multi_value_delimiter = fields.Char(
        string='Multi-value Delimiter',
        default=',',
        help='Delimiter for multiple values (used for many2many fields)',
    )
    
    # Selection field mapping
    value_mapping = fields.Text(
        string='Value Mapping',
        help='JSON mapping of source values to target values. Example: {"Old": "new", "Yes": "true"}',
    )
    
    # AI Suggestions
    ai_confidence = fields.Float(
        string='AI Confidence',
        help='Confidence score from AI mapping suggestion (0-1)',
    )
    ai_suggested = fields.Boolean(
        string='AI Suggested',
        help='This mapping was suggested by AI',
    )
    ai_reasoning = fields.Text(
        string='AI Reasoning',
        help='AI explanation for this mapping suggestion',
    )
    
    # Validation
    validation_errors = fields.Text(
        string='Validation Errors',
        readonly=True,
    )
    
    @api.depends('target_field_id')
    def _compute_is_mapped(self):
        for record in self:
            record.is_mapped = bool(record.target_field_id)
    
    @api.onchange('target_field_id')
    def _onchange_target_field(self):
        """Set defaults based on target field type."""
        if self.target_field_id:
            # Set default search field for relational fields
            if self.target_field_id.ttype in ('many2one', 'many2many'):
                self.relation_search_field = 'name'
            
            # Suggest date format for date fields
            if self.target_field_id.ttype == 'date':
                self.date_format = '%Y-%m-%d'
            elif self.target_field_id.ttype == 'datetime':
                self.date_format = '%Y-%m-%d %H:%M:%S'
    
    def action_test_mapping(self):
        """Test the mapping with sample data."""
        self.ensure_one()
        
        if not self.source_sample_values:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Sample Data'),
                    'message': _('No sample values available for testing.'),
                    'type': 'warning',
                }
            }
        
        # Get first sample value
        samples = self.source_sample_values.split('\n')
        test_value = samples[0] if samples else ''
        
        # Apply transformations
        transformer = self.env['migration.data.transformer']
        result = test_value
        
        for transform in self.transformation_ids:
            result = transformer.apply_transformation(
                result,
                transform.transformation_type,
                transform.transformation_params,
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Mapping Test Result'),
                'message': _('Input: %s\nOutput: %s') % (test_value, result),
                'type': 'info',
                'sticky': True,
            }
        }
    
    def action_edit_value_mapping(self):
        """Open wizard to edit value mappings."""
        self.ensure_one()
        
        return {
            'name': _('Edit Value Mapping'),
            'type': 'ir.actions.act_window',
            'res_model': 'migration.value.mapping.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_mapping_id': self.id,
                'default_current_mapping': self.value_mapping or '{}',
            },
        }


class MigrationTransformationRule(models.Model):
    _name = 'migration.transformation.rule'
    _description = 'Data Transformation Rule'
    _order = 'sequence, name'

    name = fields.Char(string='Rule Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    transformation_type = fields.Selection([
        # String transformations
        ('uppercase', 'Uppercase'),
        ('lowercase', 'Lowercase'),
        ('titlecase', 'Title Case'),
        ('trim', 'Trim Whitespace'),
        ('replace', 'Find & Replace'),
        ('regex_replace', 'Regex Replace'),
        ('prefix', 'Add Prefix'),
        ('suffix', 'Add Suffix'),
        ('truncate', 'Truncate'),
        ('extract', 'Extract Pattern'),
        
        # Numeric transformations
        ('round', 'Round Number'),
        ('multiply', 'Multiply'),
        ('divide', 'Divide'),
        ('add', 'Add'),
        ('subtract', 'Subtract'),
        ('abs', 'Absolute Value'),
        ('clean_numeric', 'Clean Numeric'),
        
        # Date transformations
        ('date_format', 'Reformat Date'),
        ('date_add_days', 'Add Days'),
        ('date_to_year', 'Extract Year'),
        ('date_to_month', 'Extract Month'),
        
        # Mapping transformations
        ('value_map', 'Value Mapping'),
        ('lookup', 'Lookup Table'),
        
        # Special transformations
        ('split', 'Split String'),
        ('join', 'Join Values'),
        ('coalesce', 'Use First Non-Empty'),
        ('conditional', 'Conditional'),
        ('python', 'Python Expression'),
    ], string='Transformation Type', required=True)
    
    transformation_params = fields.Text(
        string='Parameters',
        help='JSON parameters for the transformation',
    )
    
    description = fields.Text(string='Description')
    
    # Predefined flag
    is_system = fields.Boolean(
        string='System Rule',
        default=False,
        help='System-defined rules cannot be deleted',
    )
    
    @api.model
    def get_transformation_help(self, transformation_type):
        """Return help text for transformation parameters."""
        help_texts = {
            'replace': 'Parameters: {"find": "old text", "replace": "new text"}',
            'regex_replace': 'Parameters: {"pattern": "regex", "replace": "replacement"}',
            'prefix': 'Parameters: {"prefix": "text to add"}',
            'suffix': 'Parameters: {"suffix": "text to add"}',
            'truncate': 'Parameters: {"length": 50, "suffix": "..."}',
            'extract': 'Parameters: {"pattern": "regex with group"}',
            'round': 'Parameters: {"decimals": 2}',
            'multiply': 'Parameters: {"factor": 1.5}',
            'divide': 'Parameters: {"divisor": 100}',
            'add': 'Parameters: {"value": 10}',
            'subtract': 'Parameters: {"value": 5}',
            'date_format': 'Parameters: {"input_format": "%d/%m/%Y", "output_format": "%Y-%m-%d"}',
            'date_add_days': 'Parameters: {"days": 30}',
            'value_map': 'Parameters: {"mapping": {"old1": "new1", "old2": "new2"}, "default": "other"}',
            'split': 'Parameters: {"delimiter": ",", "index": 0}',
            'join': 'Parameters: {"delimiter": ", "}',
            'conditional': 'Parameters: {"condition": "value > 100", "true_value": "High", "false_value": "Low"}',
            'python': 'Parameters: {"expression": "value.strip().upper()"}',
        }
        return help_texts.get(transformation_type, 'No parameters required')
