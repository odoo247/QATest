# -*- coding: utf-8 -*-
"""
AI Import Job

Main model for managing data imports with AI-powered mapping and error handling.
"""

import base64
import csv
import json
import io
import logging
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AiImportJob(models.Model):
    """AI-powered data import job."""
    _name = 'ai.import.job'
    _description = 'AI Import Job'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'ai.kb.mixin']
    _order = 'create_date desc'

    name = fields.Char('Job Name', required=True, tracking=True,
        default=lambda self: _('New Import'))
    
    # Source file
    file_data = fields.Binary('Source File', attachment=True)
    file_name = fields.Char('Filename')
    file_type = fields.Selection([
        ('csv', 'CSV'),
        ('excel', 'Excel (xlsx)'),
        ('json', 'JSON'),
    ], string='File Type', compute='_compute_file_type', store=True)
    
    # Target
    target_model_id = fields.Many2one('ir.model', string='Target Model',
        domain="[('transient', '=', False)]",
        help='Odoo model to import data into')
    target_model_name = fields.Char(related='target_model_id.model', store=True)
    
    # Options
    update_existing = fields.Boolean('Update Existing Records',
        help='If checked, update records if they already exist (matched by key field)')
    key_field_id = fields.Many2one('ir.model.fields', string='Key Field',
        domain="[('model_id', '=', target_model_id)]",
        help='Field used to identify existing records for update')
    skip_errors = fields.Boolean('Skip Errors', default=True,
        help='Continue importing even if some rows fail')
    batch_size = fields.Integer('Batch Size', default=100,
        help='Number of records per batch (for large imports)')
    
    # Mappings
    mapping_ids = fields.One2many('ai.import.mapping', 'job_id', string='Field Mappings')
    
    # Preview data
    preview_data = fields.Text('Preview Data (JSON)', readonly=True)
    preview_html = fields.Html('Preview', compute='_compute_preview_html')
    source_columns = fields.Text('Source Columns (JSON)', readonly=True)
    
    # State & Progress
    state = fields.Selection([
        ('draft', 'Draft'),
        ('mapped', 'Mapped'),
        ('validated', 'Validated'),
        ('importing', 'Importing...'),
        ('done', 'Done'),
        ('error', 'Error'),
    ], default='draft', tracking=True)
    
    total_rows = fields.Integer('Total Rows', readonly=True)
    processed_rows = fields.Integer('Processed', readonly=True)
    success_count = fields.Integer('Successful', readonly=True)
    error_count = fields.Integer('Errors', readonly=True)
    progress = fields.Float('Progress %', compute='_compute_progress')
    
    # Errors
    error_ids = fields.One2many('ai.import.error', 'job_id', string='Errors')
    last_error = fields.Text('Last Error', readonly=True)
    
    # Timing
    started_at = fields.Datetime('Started At', readonly=True)
    completed_at = fields.Datetime('Completed At', readonly=True)
    duration = fields.Float('Duration (seconds)', compute='_compute_duration')

    @api.depends('file_name')
    def _compute_file_type(self):
        for rec in self:
            if not rec.file_name:
                rec.file_type = False
            elif rec.file_name.lower().endswith('.csv'):
                rec.file_type = 'csv'
            elif rec.file_name.lower().endswith(('.xlsx', '.xls')):
                rec.file_type = 'excel'
            elif rec.file_name.lower().endswith('.json'):
                rec.file_type = 'json'
            else:
                rec.file_type = False

    @api.depends('total_rows', 'processed_rows')
    def _compute_progress(self):
        for rec in self:
            if rec.total_rows:
                rec.progress = (rec.processed_rows / rec.total_rows) * 100
            else:
                rec.progress = 0

    @api.depends('started_at', 'completed_at')
    def _compute_duration(self):
        for rec in self:
            if rec.started_at and rec.completed_at:
                delta = rec.completed_at - rec.started_at
                rec.duration = delta.total_seconds()
            else:
                rec.duration = 0

    @api.depends('preview_data')
    def _compute_preview_html(self):
        for rec in self:
            if not rec.preview_data:
                rec.preview_html = '<p>No preview available. Upload a file first.</p>'
                continue
            
            try:
                data = json.loads(rec.preview_data)
                if not data:
                    rec.preview_html = '<p>No data in file.</p>'
                    continue
                
                # Build HTML table
                html = ['<table class="table table-sm table-bordered">']
                
                # Header
                html.append('<thead><tr>')
                for col in data[0].keys():
                    html.append(f'<th>{col}</th>')
                html.append('</tr></thead>')
                
                # Body (first 10 rows)
                html.append('<tbody>')
                for row in data[:10]:
                    html.append('<tr>')
                    for val in row.values():
                        display_val = str(val)[:50] if val else ''
                        html.append(f'<td>{display_val}</td>')
                    html.append('</tr>')
                html.append('</tbody></table>')
                
                if len(data) > 10:
                    html.append(f'<p class="text-muted">Showing 10 of {len(data)} rows</p>')
                
                rec.preview_html = ''.join(html)
            except Exception as e:
                rec.preview_html = f'<p class="text-danger">Error: {e}</p>'

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def action_parse_file(self):
        """Parse the uploaded file and extract columns/preview."""
        self.ensure_one()
        
        if not self.file_data:
            raise UserError('Please upload a file first.')
        
        try:
            data = self._parse_file()
            
            if not data:
                raise UserError('No data found in file.')
            
            # Store preview and columns
            self.write({
                'preview_data': json.dumps(data[:100], default=str),
                'source_columns': json.dumps(list(data[0].keys())),
                'total_rows': len(data),
                'state': 'draft',
            })
            
            # Auto-generate mappings
            self._generate_mappings(data[0].keys())
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'File Parsed',
                    'message': f'Found {len(data)} rows, {len(data[0])} columns',
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.exception('Error parsing file')
            raise UserError(f'Error parsing file: {e}')

    def action_auto_map(self):
        """Auto-map source columns to target fields using AI/KB."""
        self.ensure_one()
        
        if not self.target_model_id:
            raise UserError('Please select a target model first.')
        
        if not self.source_columns:
            raise UserError('Please parse the file first.')
        
        source_cols = json.loads(self.source_columns)
        target_fields = self._get_target_fields()
        
        # Get model schema from KB if available
        kb_schema = self._get_kb_schema()
        
        mapped_count = 0
        for mapping in self.mapping_ids:
            if mapping.target_field_id:
                continue  # Already mapped
            
            source_col = mapping.source_column.lower().strip()
            
            # Try exact match
            for field_name, field_info in target_fields.items():
                field_label = (field_info.get('string') or '').lower()
                
                if source_col == field_name or source_col == field_label:
                    field = self.env['ir.model.fields'].search([
                        ('model_id', '=', self.target_model_id.id),
                        ('name', '=', field_name),
                    ], limit=1)
                    if field:
                        mapping.target_field_id = field.id
                        mapping.confidence = 'high'
                        mapped_count += 1
                        break
            
            # Try fuzzy match
            if not mapping.target_field_id:
                best_match = self._fuzzy_match_field(source_col, target_fields)
                if best_match:
                    field = self.env['ir.model.fields'].search([
                        ('model_id', '=', self.target_model_id.id),
                        ('name', '=', best_match),
                    ], limit=1)
                    if field:
                        mapping.target_field_id = field.id
                        mapping.confidence = 'medium'
                        mapped_count += 1
        
        if self.mapping_ids.filtered('target_field_id'):
            self.state = 'mapped'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Auto-Mapping Complete',
                'message': f'Mapped {mapped_count} fields automatically',
                'type': 'success',
            }
        }

    def action_validate(self):
        """Validate data before import."""
        self.ensure_one()
        
        if not self.mapping_ids.filtered('target_field_id'):
            raise UserError('Please map at least one field.')
        
        data = self._parse_file()
        errors = []
        
        # Get field info
        target_fields = self._get_target_fields()
        
        for idx, row in enumerate(data[:100], 1):  # Validate first 100 rows
            row_errors = self._validate_row(row, idx, target_fields)
            errors.extend(row_errors)
        
        if errors:
            # Create error records
            self.error_ids.unlink()
            for err in errors[:50]:  # Keep first 50 validation errors
                self.env['ai.import.error'].create({
                    'job_id': self.id,
                    'row_number': err['row'],
                    'field_name': err.get('field'),
                    'error_type': 'validation',
                    'error_message': err['message'],
                    'source_value': err.get('value'),
                })
            
            self.state = 'error'
            self.last_error = f"Validation failed: {len(errors)} errors found"
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Validation Failed',
                    'message': f'{len(errors)} validation errors found',
                    'type': 'warning',
                }
            }
        
        self.state = 'validated'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Validation Passed',
                'message': 'Data is ready for import',
                'type': 'success',
            }
        }

    def action_import(self):
        """Execute the import."""
        self.ensure_one()
        
        if self.state not in ('mapped', 'validated'):
            raise UserError('Please map fields and validate before importing.')
        
        self.write({
            'state': 'importing',
            'started_at': fields.Datetime.now(),
            'processed_rows': 0,
            'success_count': 0,
            'error_count': 0,
        })
        self.error_ids.unlink()
        
        # Parse file
        data = self._parse_file()
        
        # Get mappings
        mappings = {}
        for m in self.mapping_ids.filtered('target_field_id'):
            mappings[m.source_column] = {
                'field': m.target_field_id.name,
                'field_type': m.target_field_id.ttype,
                'relation': m.target_field_id.relation,
                'transform': m.transform,
            }
        
        if not mappings:
            raise UserError('No field mappings defined.')
        
        # Import in batches
        Model = self.env[self.target_model_name]
        batch_size = self.batch_size or 100
        
        success = 0
        errors = 0
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            
            for idx, row in enumerate(batch, i + 1):
                try:
                    vals = self._prepare_values(row, mappings)
                    
                    if self.update_existing and self.key_field_id:
                        # Try to find existing record
                        key_value = vals.get(self.key_field_id.name)
                        if key_value:
                            existing = Model.search([
                                (self.key_field_id.name, '=', key_value)
                            ], limit=1)
                            if existing:
                                existing.write(vals)
                                success += 1
                                continue
                    
                    Model.create(vals)
                    success += 1
                    
                except Exception as e:
                    errors += 1
                    error_msg = str(e)
                    
                    # Check KB for known fix
                    kb_fix = self._lookup_kb_error(error_msg)
                    
                    self.env['ai.import.error'].create({
                        'job_id': self.id,
                        'row_number': idx,
                        'error_type': 'import',
                        'error_message': error_msg,
                        'source_data': json.dumps(row, default=str),
                        'kb_suggestion': kb_fix,
                    })
                    
                    if not self.skip_errors:
                        self.write({
                            'state': 'error',
                            'last_error': error_msg,
                            'processed_rows': idx,
                            'success_count': success,
                            'error_count': errors,
                        })
                        raise UserError(f'Import failed at row {idx}: {error_msg}')
            
            # Update progress
            self.write({
                'processed_rows': min(i + batch_size, len(data)),
                'success_count': success,
                'error_count': errors,
            })
            self.env.cr.commit()
        
        self.write({
            'state': 'done' if errors == 0 else 'error',
            'completed_at': fields.Datetime.now(),
            'last_error': f'{errors} errors during import' if errors else False,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Complete',
                'message': f'Imported {success} records, {errors} errors',
                'type': 'success' if errors == 0 else 'warning',
            }
        }

    def action_reset(self):
        """Reset job to draft state."""
        self.ensure_one()
        self.write({
            'state': 'draft',
            'processed_rows': 0,
            'success_count': 0,
            'error_count': 0,
            'last_error': False,
            'started_at': False,
            'completed_at': False,
        })
        self.error_ids.unlink()

    def action_learn_from_errors(self):
        """Record errors to KB for future learning."""
        self.ensure_one()
        
        if not self.error_ids:
            raise UserError('No errors to learn from.')
        
        # Group similar errors
        error_groups = {}
        for err in self.error_ids.filtered(lambda e: e.error_type == 'import'):
            # Normalize error message
            key = self._normalize_error(err.error_message)
            if key not in error_groups:
                error_groups[key] = []
            error_groups[key].append(err)
        
        recorded = 0
        for error_pattern, errors in error_groups.items():
            if len(errors) >= 2:  # Only learn from repeated errors
                # Record to KB
                self.kb_record_error(
                    version=self.env['ir.module.module'].search([
                        ('name', '=', 'base')
                    ], limit=1).installed_version or '18.0',
                    task_type='import',
                    error_text=errors[0].error_message,
                    wrong_code=errors[0].source_data or '',
                )
                recorded += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Learning Complete',
                'message': f'Recorded {recorded} error patterns to KB',
                'type': 'success',
            }
        }

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _parse_file(self):
        """Parse the source file and return list of dicts."""
        self.ensure_one()
        
        if not self.file_data:
            return []
        
        content = base64.b64decode(self.file_data)
        
        if self.file_type == 'csv':
            return self._parse_csv(content)
        elif self.file_type == 'excel':
            return self._parse_excel(content)
        elif self.file_type == 'json':
            return self._parse_json(content)
        else:
            raise UserError(f'Unsupported file type: {self.file_name}')

    def _parse_csv(self, content):
        """Parse CSV content."""
        # Try to detect encoding
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = content.decode('latin-1')
        
        # Detect delimiter
        sample = text[:2000]
        if '\t' in sample and sample.count('\t') > sample.count(','):
            delimiter = '\t'
        elif ';' in sample and sample.count(';') > sample.count(','):
            delimiter = ';'
        else:
            delimiter = ','
        
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        return list(reader)

    def _parse_excel(self, content):
        """Parse Excel content."""
        try:
            import openpyxl
        except ImportError:
            raise UserError('Please install openpyxl: pip install openpyxl')
        
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
        ws = wb.active
        
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        
        headers = [str(h or f'col_{i}') for i, h in enumerate(rows[0])]
        data = []
        for row in rows[1:]:
            if any(row):  # Skip empty rows
                data.append(dict(zip(headers, row)))
        
        return data

    def _parse_json(self, content):
        """Parse JSON content."""
        data = json.loads(content.decode('utf-8'))
        
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Could be {records: [...]} or single record
            if 'records' in data:
                return data['records']
            elif 'data' in data:
                return data['data']
            else:
                return [data]
        return []

    def _generate_mappings(self, columns):
        """Generate mapping records for each source column."""
        self.mapping_ids.unlink()
        
        for col in columns:
            self.env['ai.import.mapping'].create({
                'job_id': self.id,
                'source_column': col,
            })

    def _get_target_fields(self):
        """Get target model fields info."""
        if not self.target_model_id:
            return {}
        
        Model = self.env[self.target_model_name]
        return Model.fields_get()

    def _get_kb_schema(self):
        """Get model schema from Knowledge Base."""
        if not self.target_model_name:
            return None
        
        try:
            Schema = self.env['ai.model.schema']
            schema = Schema.search([
                ('model_name', '=', self.target_model_name),
            ], limit=1, order='odoo_version desc')
            
            if schema and schema.fields_json:
                return json.loads(schema.fields_json)
        except Exception:
            pass
        
        return None

    def _fuzzy_match_field(self, source_col, target_fields):
        """Try to fuzzy match a source column to target fields."""
        source_clean = source_col.lower().replace('_', '').replace(' ', '')
        
        best_match = None
        best_score = 0
        
        for field_name, field_info in target_fields.items():
            # Skip internal fields
            if field_name.startswith('_') or field_name in ('id', 'create_uid', 'write_uid', 'create_date', 'write_date'):
                continue
            
            field_clean = field_name.lower().replace('_', '')
            label_clean = (field_info.get('string') or '').lower().replace(' ', '')
            
            # Check containment
            if source_clean in field_clean or field_clean in source_clean:
                score = len(source_clean) / max(len(field_clean), 1)
                if score > best_score:
                    best_score = score
                    best_match = field_name
            
            if source_clean in label_clean or label_clean in source_clean:
                score = len(source_clean) / max(len(label_clean), 1)
                if score > best_score:
                    best_score = score
                    best_match = field_name
        
        return best_match if best_score > 0.5 else None

    def _validate_row(self, row, row_num, target_fields):
        """Validate a single row of data."""
        errors = []
        
        for mapping in self.mapping_ids.filtered('target_field_id'):
            field_name = mapping.target_field_id.name
            field_info = target_fields.get(field_name, {})
            source_value = row.get(mapping.source_column)
            
            # Check required
            if field_info.get('required') and not source_value:
                errors.append({
                    'row': row_num,
                    'field': field_name,
                    'message': f"Required field '{field_name}' is empty",
                    'value': source_value,
                })
            
            # Check type
            if source_value:
                field_type = field_info.get('type')
                if field_type in ('integer', 'float', 'monetary'):
                    try:
                        float(str(source_value).replace(',', ''))
                    except ValueError:
                        errors.append({
                            'row': row_num,
                            'field': field_name,
                            'message': f"Invalid number for '{field_name}': {source_value}",
                            'value': source_value,
                        })
        
        return errors

    def _prepare_values(self, row, mappings):
        """Prepare values dict for create/write."""
        vals = {}
        
        for source_col, mapping_info in mappings.items():
            value = row.get(source_col)
            
            if value is None or value == '':
                continue
            
            field_name = mapping_info['field']
            field_type = mapping_info['field_type']
            transform = mapping_info.get('transform')
            
            # Apply transform
            if transform:
                value = self._apply_transform(value, transform)
            
            # Convert based on type
            if field_type in ('integer',):
                try:
                    value = int(float(str(value).replace(',', '')))
                except (ValueError, TypeError):
                    continue
            
            elif field_type in ('float', 'monetary'):
                try:
                    value = float(str(value).replace(',', ''))
                except (ValueError, TypeError):
                    continue
            
            elif field_type == 'boolean':
                value = str(value).lower() in ('true', '1', 'yes', 'y', 'x')
            
            elif field_type == 'date':
                value = self._parse_date(value)
                if not value:
                    continue
            
            elif field_type == 'datetime':
                value = self._parse_datetime(value)
                if not value:
                    continue
            
            elif field_type == 'many2one':
                # Try to find related record
                relation = mapping_info.get('relation')
                if relation:
                    value = self._resolve_many2one(relation, value)
                    if not value:
                        continue
            
            elif field_type in ('one2many', 'many2many'):
                continue  # Skip relational fields for now
            
            else:
                value = str(value) if value else ''
            
            vals[field_name] = value
        
        return vals

    def _apply_transform(self, value, transform):
        """Apply a transform to a value."""
        if transform == 'upper':
            return str(value).upper()
        elif transform == 'lower':
            return str(value).lower()
        elif transform == 'strip':
            return str(value).strip()
        elif transform == 'title':
            return str(value).title()
        return value

    def _parse_date(self, value):
        """Parse date from various formats."""
        if not value:
            return None
        
        if hasattr(value, 'strftime'):  # Already a date object
            return value.strftime('%Y-%m-%d')
        
        formats = [
            '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y',
            '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%Y',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(str(value), fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        return None

    def _parse_datetime(self, value):
        """Parse datetime from various formats."""
        if not value:
            return None
        
        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        
        formats = [
            '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%m/%d/%Y %H:%M:%S',
            '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(str(value), fmt).strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
        
        # Try date only
        date_val = self._parse_date(value)
        return f'{date_val} 00:00:00' if date_val else None

    def _resolve_many2one(self, relation, value):
        """Resolve a many2one value to record ID."""
        if not value:
            return None
        
        # If already an ID
        if isinstance(value, int):
            return value
        
        try:
            int_val = int(value)
            return int_val
        except (ValueError, TypeError):
            pass
        
        # Search by name
        try:
            Model = self.env[relation]
            record = Model.search([('name', '=', str(value))], limit=1)
            if record:
                return record.id
            
            # Try ilike
            record = Model.search([('name', 'ilike', str(value))], limit=1)
            if record:
                return record.id
        except Exception:
            pass
        
        return None

    def _lookup_kb_error(self, error_message):
        """Look up error in KB for known fixes."""
        try:
            patterns = self.kb_get_error_patterns(error_message, 'import')
            if patterns:
                return patterns[0].get('fix') or patterns[0].get('explanation')
        except Exception:
            pass
        return None

    def _normalize_error(self, error_message):
        """Normalize error message for grouping."""
        import re
        # Remove specific values like IDs, names
        normalized = re.sub(r"'[^']*'", "'X'", error_message)
        normalized = re.sub(r"\d+", "N", normalized)
        return normalized[:200]
