import json
import logging
import re

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MigrationAIService(models.AbstractModel):
    _name = 'migration.ai.service'
    _description = 'AI Service for Data Migration'

    @api.model
    def get_api_key(self, provider, project_api_key=None):
        """Get API key from project or system parameters."""
        if project_api_key:
            return project_api_key
        
        param_name = f'migration.ai.{provider}_api_key'
        api_key = self.env['ir.config_parameter'].sudo().get_param(param_name)
        
        if not api_key:
            raise UserError(_(
                'AI API key not configured. Please set the API key in the project settings '
                'or configure the system parameter: %s'
            ) % param_name)
        
        return api_key
    
    @api.model
    def suggest_mappings(self, project):
        """
        Use AI to suggest field mappings for a migration project.
        
        Returns a list of mapping suggestions with confidence scores.
        """
        provider = project.ai_provider or 'anthropic'
        api_key = self.get_api_key(provider, project.ai_api_key)
        
        # Get source columns and sample data
        source_columns = json.loads(project.source_columns) if project.source_columns else []
        preview_data = json.loads(project.preview_data) if project.preview_data else []
        
        # Get target model fields
        target_fields = self._get_target_fields(project.target_model_id)
        
        # Build prompt
        prompt = self._build_mapping_prompt(
            source_columns,
            preview_data,
            target_fields,
            project.target_model_id.name,
        )
        
        # Call AI service
        if provider == 'anthropic':
            response = self._call_anthropic(api_key, prompt)
        else:
            response = self._call_openai(api_key, prompt)
        
        # Parse response
        suggestions = self._parse_mapping_response(response, source_columns, target_fields)
        
        return suggestions
    
    def _get_target_fields(self, model_id):
        """Get relevant fields from target model."""
        fields = self.env['ir.model.fields'].search([
            ('model_id', '=', model_id.id),
            ('name', 'not in', [
                'id', 'create_uid', 'create_date', 'write_uid', 'write_date',
                '__last_update', 'display_name', 'message_ids', 'message_follower_ids',
                'message_channel_ids', 'message_partner_ids', 'activity_ids',
            ]),
            ('store', '=', True),
        ])
        
        return [{
            'name': f.name,
            'label': f.field_description,
            'type': f.ttype,
            'required': f.required,
            'relation': f.relation or '',
            'help': f.help or '',
        } for f in fields]
    
    def _build_mapping_prompt(self, source_columns, preview_data, target_fields, model_name):
        """Build the prompt for AI mapping suggestions."""
        
        # Format sample data
        sample_data_str = ""
        if preview_data:
            for i, row in enumerate(preview_data[:3]):
                sample_data_str += f"\nRow {i+1}:\n"
                for col in source_columns:
                    value = row.get(col, '')
                    sample_data_str += f"  {col}: {value}\n"
        
        # Format target fields
        target_fields_str = ""
        for field in target_fields:
            required_str = " (REQUIRED)" if field['required'] else ""
            relation_str = f" -> {field['relation']}" if field['relation'] else ""
            target_fields_str += f"  - {field['name']} ({field['label']}): {field['type']}{relation_str}{required_str}\n"
            if field['help']:
                target_fields_str += f"    Help: {field['help']}\n"
        
        prompt = f"""You are a data migration expert. Analyze the source data columns and suggest mappings to the target Odoo model fields.

TARGET MODEL: {model_name}

SOURCE COLUMNS:
{', '.join(source_columns)}

SAMPLE DATA:
{sample_data_str}

TARGET FIELDS:
{target_fields_str}

TASK: For each source column, suggest the best matching target field. Consider:
1. Column name similarity
2. Data type compatibility
3. Sample value patterns
4. Required fields must be mapped if possible

RESPONSE FORMAT (JSON):
{{
    "mappings": [
        {{
            "source_column": "column_name",
            "target_field": "field_name",
            "confidence": 0.95,
            "reasoning": "Brief explanation",
            "transformations": ["optional transformation suggestions"],
            "value_mapping": {{"source_val": "target_val"}} // optional for selection fields
        }},
        ...
    ],
    "warnings": ["Any concerns or issues"],
    "unmapped_required": ["Required fields that couldn't be mapped"]
}}

Important:
- Only suggest mappings you're confident about
- Set confidence between 0 and 1
- For date fields, suggest the date format detected
- For selection/many2one fields, note if value mapping is needed
- If a source column doesn't match any field, omit it or set target_field to null

Respond ONLY with the JSON, no additional text."""

        return prompt
    
    def _call_anthropic(self, api_key, prompt):
        """Call Anthropic Claude API."""
        try:
            import requests
        except ImportError:
            raise UserError(_('requests library is required. Install with: pip install requests'))
        
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
        }
        
        data = {
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 4096,
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
        }
        
        try:
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=data,
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            return result['content'][0]['text']
        except requests.exceptions.RequestException as e:
            _logger.error(f"Anthropic API error: {e}")
            raise UserError(_('AI service error: %s') % str(e))
    
    def _call_openai(self, api_key, prompt):
        """Call OpenAI API."""
        try:
            import requests
        except ImportError:
            raise UserError(_('requests library is required. Install with: pip install requests'))
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }
        
        data = {
            'model': 'gpt-4-turbo-preview',
            'messages': [
                {'role': 'system', 'content': 'You are a data migration expert. Respond only with valid JSON.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.1,
            'max_tokens': 4096,
        }
        
        try:
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except requests.exceptions.RequestException as e:
            _logger.error(f"OpenAI API error: {e}")
            raise UserError(_('AI service error: %s') % str(e))
    
    def _parse_mapping_response(self, response, source_columns, target_fields):
        """Parse the AI response into structured mapping suggestions."""
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response.strip()
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            _logger.error(f"Failed to parse AI response: {e}\nResponse: {response}")
            raise UserError(_('Failed to parse AI response. Please try again.'))
        
        # Build lookup for target fields
        target_field_map = {f['name']: f for f in target_fields}
        
        suggestions = []
        for mapping in data.get('mappings', []):
            source_col = mapping.get('source_column')
            target_field = mapping.get('target_field')
            
            if not source_col or source_col not in source_columns:
                continue
            
            if target_field and target_field not in target_field_map:
                continue
            
            suggestions.append({
                'source_column': source_col,
                'target_field': target_field,
                'confidence': mapping.get('confidence', 0.5),
                'reasoning': mapping.get('reasoning', ''),
                'transformations': mapping.get('transformations', []),
                'value_mapping': mapping.get('value_mapping'),
                'date_format': mapping.get('date_format'),
            })
        
        return {
            'suggestions': suggestions,
            'warnings': data.get('warnings', []),
            'unmapped_required': data.get('unmapped_required', []),
        }
    
    @api.model
    def suggest_transformations(self, source_value, source_column, target_field):
        """
        Suggest transformations for a specific field mapping.
        """
        prompt = f"""Analyze this data transformation need:

Source Column: {source_column}
Sample Value: {source_value}
Target Field: {target_field.get('name')} ({target_field.get('type')})

Suggest specific transformations needed to convert the source value to the target field type.

RESPONSE FORMAT (JSON):
{{
    "transformations": [
        {{
            "type": "transformation_type",
            "params": {{}},
            "description": "What this does"
        }}
    ],
    "example_output": "What the transformed value would look like"
}}

Available transformation types:
- uppercase, lowercase, titlecase, trim
- replace (params: find, replace)
- prefix, suffix (params: prefix/suffix)
- truncate (params: length)
- round (params: decimals)
- multiply, divide, add, subtract (params: factor/value)
- date_format (params: input_format, output_format)
- value_map (params: mapping dict)

Respond ONLY with JSON."""

        # For now, return a simple heuristic-based suggestion
        # In production, this would call the AI service
        
        suggestions = []
        
        if target_field.get('type') in ('date', 'datetime'):
            suggestions.append({
                'type': 'date_format',
                'params': {'input_format': '%d/%m/%Y', 'output_format': '%Y-%m-%d'},
                'description': 'Convert date format',
            })
        
        if target_field.get('type') == 'float' and isinstance(source_value, str):
            if '$' in source_value or '€' in source_value:
                suggestions.append({
                    'type': 'replace',
                    'params': {'find': r'[$€,]', 'replace': ''},
                    'description': 'Remove currency symbols',
                })
        
        return suggestions
    
    @api.model
    def analyze_data_quality(self, project):
        """
        Use AI to analyze data quality issues in the source data.
        """
        source_columns = json.loads(project.source_columns) if project.source_columns else []
        preview_data = json.loads(project.preview_data) if project.preview_data else []
        
        prompt = f"""Analyze this data for quality issues:

COLUMNS: {', '.join(source_columns)}

SAMPLE DATA:
{json.dumps(preview_data, indent=2)}

Identify:
1. Missing values
2. Inconsistent formats
3. Potential duplicates
4. Data type issues
5. Outliers or anomalies

RESPONSE FORMAT (JSON):
{{
    "issues": [
        {{
            "column": "column_name",
            "issue_type": "missing_values|format_inconsistency|duplicates|type_mismatch|outlier",
            "severity": "high|medium|low",
            "description": "Description of the issue",
            "recommendation": "How to fix it"
        }}
    ],
    "overall_quality_score": 0.85,
    "summary": "Brief summary of data quality"
}}

Respond ONLY with JSON."""

        provider = project.ai_provider or 'anthropic'
        api_key = self.get_api_key(provider, project.ai_api_key)
        
        if provider == 'anthropic':
            response = self._call_anthropic(api_key, prompt)
        else:
            response = self._call_openai(api_key, prompt)
        
        # Parse response
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response.strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {
                'issues': [],
                'overall_quality_score': 0,
                'summary': 'Failed to analyze data quality',
            }
