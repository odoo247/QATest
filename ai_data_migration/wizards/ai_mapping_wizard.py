import json
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MigrationAIMappingWizard(models.TransientModel):
    _name = 'migration.ai.mapping.wizard'
    _description = 'AI Field Mapping Wizard'

    project_id = fields.Many2one(
        'migration.project',
        string='Migration Project',
        required=True,
    )
    
    state = fields.Selection([
        ('configure', 'Configure'),
        ('analyzing', 'Analyzing'),
        ('review', 'Review Suggestions'),
        ('complete', 'Complete'),
    ], default='configure', string='State')
    
    # AI Configuration
    ai_provider = fields.Selection([
        ('anthropic', 'Anthropic Claude'),
        ('openai', 'OpenAI GPT'),
    ], string='AI Provider', default='anthropic')
    
    ai_api_key = fields.Char(
        string='API Key',
        help='Leave empty to use system configuration',
    )
    
    # Analysis options
    include_data_quality = fields.Boolean(
        string='Include Data Quality Analysis',
        default=True,
    )
    
    auto_create_mappings = fields.Boolean(
        string='Auto-create High Confidence Mappings',
        default=True,
        help='Automatically create mappings with confidence > 0.8',
    )
    
    confidence_threshold = fields.Float(
        string='Confidence Threshold',
        default=0.8,
        help='Minimum confidence for auto-creation',
    )
    
    # Results
    suggestions_json = fields.Text(string='Suggestions JSON')
    suggestions_html = fields.Html(string='Suggestions', readonly=True)
    
    warnings_text = fields.Text(string='Warnings', readonly=True)
    data_quality_html = fields.Html(string='Data Quality Analysis', readonly=True)
    
    # Suggestion lines for user review
    suggestion_line_ids = fields.One2many(
        'migration.ai.mapping.wizard.line',
        'wizard_id',
        string='Mapping Suggestions',
    )
    
    def action_analyze(self):
        """Run AI analysis on the source data."""
        self.ensure_one()
        
        self.state = 'analyzing'
        
        # Update project AI settings
        self.project_id.write({
            'ai_provider': self.ai_provider,
            'ai_api_key': self.ai_api_key,
        })
        
        # Get AI suggestions
        ai_service = self.env['migration.ai.service']
        
        try:
            result = ai_service.suggest_mappings(self.project_id)
        except Exception as e:
            raise UserError(_('AI Analysis Failed: %s') % str(e))
        
        # Store results
        self.suggestions_json = json.dumps(result, indent=2)
        
        # Create suggestion lines
        self.suggestion_line_ids.unlink()
        
        source_columns = json.loads(self.project_id.source_columns)
        preview_data = json.loads(self.project_id.preview_data) if self.project_id.preview_data else []
        
        for suggestion in result.get('suggestions', []):
            # Get sample values for this column
            sample_values = []
            for row in preview_data[:5]:
                val = row.get(suggestion['source_column'], '')
                if val and val not in sample_values:
                    sample_values.append(str(val))
            
            # Find target field
            target_field = None
            if suggestion['target_field']:
                target_field = self.env['ir.model.fields'].search([
                    ('model_id', '=', self.project_id.target_model_id.id),
                    ('name', '=', suggestion['target_field']),
                ], limit=1)
            
            self.env['migration.ai.mapping.wizard.line'].create({
                'wizard_id': self.id,
                'source_column': suggestion['source_column'],
                'sample_values': '\n'.join(sample_values[:3]),
                'target_field_id': target_field.id if target_field else False,
                'confidence': suggestion['confidence'],
                'reasoning': suggestion.get('reasoning', ''),
                'accepted': suggestion['confidence'] >= self.confidence_threshold and self.auto_create_mappings,
                'transformations_suggested': json.dumps(suggestion.get('transformations', [])),
                'value_mapping_suggested': json.dumps(suggestion.get('value_mapping')) if suggestion.get('value_mapping') else False,
            })
        
        # Handle unmapped source columns
        mapped_columns = [s['source_column'] for s in result.get('suggestions', [])]
        for col in source_columns:
            if col not in mapped_columns:
                sample_values = []
                for row in preview_data[:5]:
                    val = row.get(col, '')
                    if val and val not in sample_values:
                        sample_values.append(str(val))
                
                self.env['migration.ai.mapping.wizard.line'].create({
                    'wizard_id': self.id,
                    'source_column': col,
                    'sample_values': '\n'.join(sample_values[:3]),
                    'confidence': 0,
                    'reasoning': 'No matching field found',
                    'accepted': False,
                })
        
        # Process warnings
        if result.get('warnings'):
            self.warnings_text = '\n'.join(result['warnings'])
        
        if result.get('unmapped_required'):
            warning = _('Required fields not mapped: %s') % ', '.join(result['unmapped_required'])
            self.warnings_text = (self.warnings_text + '\n' + warning) if self.warnings_text else warning
        
        # Run data quality analysis if requested
        if self.include_data_quality:
            try:
                quality_result = ai_service.analyze_data_quality(self.project_id)
                self.data_quality_html = self._format_data_quality(quality_result)
            except Exception as e:
                _logger.warning(f"Data quality analysis failed: {e}")
        
        self.state = 'review'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def _format_data_quality(self, quality_result):
        """Format data quality analysis as HTML."""
        html = '<div class="data-quality-report">'
        
        score = quality_result.get('overall_quality_score', 0)
        score_color = 'green' if score > 0.8 else 'orange' if score > 0.5 else 'red'
        
        html += f'''
            <div style="margin-bottom: 15px;">
                <strong>Overall Quality Score:</strong>
                <span style="color: {score_color}; font-size: 1.2em; font-weight: bold;">
                    {score * 100:.0f}%
                </span>
            </div>
        '''
        
        if quality_result.get('summary'):
            html += f'<p>{quality_result["summary"]}</p>'
        
        issues = quality_result.get('issues', [])
        if issues:
            html += '<h4>Issues Found:</h4><ul>'
            for issue in issues:
                severity_color = {
                    'high': 'red',
                    'medium': 'orange',
                    'low': 'gray'
                }.get(issue.get('severity'), 'gray')
                
                html += f'''
                    <li style="margin-bottom: 10px;">
                        <strong style="color: {severity_color};">[{issue.get('severity', 'unknown').upper()}]</strong>
                        <strong>{issue.get('column', 'Unknown')}:</strong>
                        {issue.get('description', '')}
                        <br/><em>Recommendation: {issue.get('recommendation', 'N/A')}</em>
                    </li>
                '''
            html += '</ul>'
        else:
            html += '<p style="color: green;">No significant issues found!</p>'
        
        html += '</div>'
        return html
    
    def action_apply_mappings(self):
        """Apply accepted mappings to the project."""
        self.ensure_one()
        
        # Clear existing mappings
        self.project_id.mapping_ids.unlink()
        
        # Create mappings from accepted suggestions
        created_count = 0
        for line in self.suggestion_line_ids.filtered(lambda l: l.accepted):
            vals = {
                'project_id': self.project_id.id,
                'source_column': line.source_column,
                'target_field_id': line.target_field_id.id if line.target_field_id else False,
                'source_sample_values': line.sample_values,
                'ai_suggested': True,
                'ai_confidence': line.confidence,
                'ai_reasoning': line.reasoning,
            }
            
            # Handle value mapping
            if line.value_mapping_suggested:
                vals['value_mapping'] = line.value_mapping_suggested
            
            self.env['migration.mapping'].create(vals)
            created_count += 1
        
        # Update project state
        self.project_id.state = 'mapping'
        self.state = 'complete'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Mappings Applied'),
                'message': _('%d field mappings created. Please review and adjust as needed.') % created_count,
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'migration.project',
                    'res_id': self.project_id.id,
                    'view_mode': 'form',
                }
            }
        }
    
    def action_select_all(self):
        """Select all suggestions."""
        self.suggestion_line_ids.write({'accepted': True})
        return self._reload_wizard()
    
    def action_select_none(self):
        """Deselect all suggestions."""
        self.suggestion_line_ids.write({'accepted': False})
        return self._reload_wizard()
    
    def action_select_high_confidence(self):
        """Select only high confidence suggestions."""
        for line in self.suggestion_line_ids:
            line.accepted = line.confidence >= self.confidence_threshold
        return self._reload_wizard()
    
    def _reload_wizard(self):
        """Reload the wizard to show updated state."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class MigrationAIMappingWizardLine(models.TransientModel):
    _name = 'migration.ai.mapping.wizard.line'
    _description = 'AI Mapping Suggestion Line'
    _order = 'confidence desc, source_column'

    wizard_id = fields.Many2one(
        'migration.ai.mapping.wizard',
        string='Wizard',
        ondelete='cascade',
    )
    
    # Source
    source_column = fields.Char(string='Source Column', readonly=True)
    sample_values = fields.Text(string='Sample Values', readonly=True)
    
    # Target
    target_field_id = fields.Many2one(
        'ir.model.fields',
        string='Target Field',
    )
    
    # AI Analysis
    confidence = fields.Float(string='Confidence', readonly=True)
    confidence_display = fields.Char(
        string='Confidence',
        compute='_compute_confidence_display',
    )
    reasoning = fields.Text(string='AI Reasoning', readonly=True)
    
    # Suggested transformations
    transformations_suggested = fields.Text(string='Suggested Transformations')
    value_mapping_suggested = fields.Text(string='Suggested Value Mapping')
    
    # User decision
    accepted = fields.Boolean(string='Accept', default=False)
    
    @api.depends('confidence')
    def _compute_confidence_display(self):
        for record in self:
            pct = record.confidence * 100
            if pct >= 80:
                record.confidence_display = f'🟢 {pct:.0f}%'
            elif pct >= 50:
                record.confidence_display = f'🟡 {pct:.0f}%'
            else:
                record.confidence_display = f'🔴 {pct:.0f}%'
