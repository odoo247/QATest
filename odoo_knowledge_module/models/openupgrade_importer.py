# -*- coding: utf-8 -*-
"""
OpenUpgrade Analysis Importer

Imports breaking changes from OCA/OpenUpgrade analysis files.

The OpenUpgrade project maintains detailed analysis files that document
every field, method, and XML ID change between Odoo versions.

Analysis file format examples:
    sale / sale.order / old_field (char): DEL
    sale / sale.order / new_field (char): NEW required
    account / account.move / state (selection): selection_keys changed
    base / res.partner / name (char): now required
    DEL ir.ui.view: sale.sale_product_configurator_view_form
    NEW ir.model.access: sale.access_sale_order_user

GitHub locations:
    - 14.0+: openupgrade_scripts/scripts/{module}/{version}/openupgrade_analysis.txt
    - 13.0-: addons/{module}/migrations/{version}/openupgrade_analysis.txt
"""

import re
import logging
import base64
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OpenUpgradeImporter(models.Model):
    """Import breaking changes from OpenUpgrade analysis files."""
    _name = 'ai.openupgrade.importer'
    _description = 'OpenUpgrade Importer'
    _order = 'create_date desc'

    name = fields.Char('Name', required=True, default='OpenUpgrade Import')
    
    # Import source
    source_type = fields.Selection([
        ('file', 'Upload File'),
        ('text', 'Paste Text'),
        ('github', 'GitHub (Manual Clone)'),
    ], string='Source', default='file', required=True)
    
    # Target version (the version being upgraded TO)
    to_version = fields.Selection([
        ('14.0', '14.0'), ('15.0', '15.0'), ('16.0', '16.0'),
        ('17.0', '17.0'), ('18.0', '18.0'), ('19.0', '19.0'),
    ], string='To Version', required=True, default='18.0')
    
    # File upload
    file_data = fields.Binary('Analysis File')
    file_name = fields.Char('Filename')
    
    # Text paste
    analysis_text = fields.Text('Analysis Text',
        help='Paste the contents of openupgrade_analysis.txt here')
    
    # GitHub clone path
    github_path = fields.Char('Local Clone Path',
        help='Path to local OpenUpgrade clone, e.g., /opt/OpenUpgrade')
    
    # Module filter (optional)
    module_filter = fields.Char('Module Filter',
        help='Comma-separated list of modules to import (empty = all)')
    
    # Results
    state = fields.Selection([
        ('draft', 'Draft'),
        ('importing', 'Importing...'),
        ('done', 'Done'),
        ('error', 'Error'),
    ], default='draft')
    
    imported_count = fields.Integer('Imported', readonly=True)
    skipped_count = fields.Integer('Skipped', readonly=True)
    error_message = fields.Text('Error')
    import_log = fields.Text('Import Log', readonly=True)
    
    # Preview
    preview_ids = fields.One2many('ai.openupgrade.importer.line', 'importer_id',
        string='Preview')

    def action_parse_preview(self):
        """Parse the analysis file and show preview."""
        self.ensure_one()
        
        # Get text content
        text = self._get_analysis_text()
        if not text:
            raise UserError('No analysis text provided.')
        
        # Clear existing preview
        self.preview_ids.unlink()
        
        # Parse the text
        parser = OpenUpgradeParser(self.to_version)
        changes = parser.parse(text)
        
        # Apply module filter
        if self.module_filter:
            allowed_modules = [m.strip() for m in self.module_filter.split(',')]
            changes = [c for c in changes if c.get('module') in allowed_modules]
        
        # Create preview lines
        preview_data = []
        for change in changes:
            preview_data.append({
                'importer_id': self.id,
                'category': change.get('category'),
                'module': change.get('module'),
                'model_name': change.get('model_name'),
                'field_name': change.get('field_name'),
                'method_name': change.get('method_name'),
                'change_type': change.get('change_type'),
                'description': change.get('description'),
                'old_code': change.get('old_code'),
                'new_code': change.get('new_code'),
                'selected': change.get('category') in ('field_remove', 'field_rename', 'method_remove', 'method_rename'),
            })
        
        if preview_data:
            self.env['ai.openupgrade.importer.line'].create(preview_data)
        
        self.write({
            'state': 'draft',
            'import_log': f"Parsed {len(changes)} changes. Review and click Import.",
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_import(self):
        """Import selected changes to Knowledge Base."""
        self.ensure_one()
        
        if not self.preview_ids:
            raise UserError('No changes to import. Click "Parse & Preview" first.')
        
        selected = self.preview_ids.filtered('selected')
        if not selected:
            raise UserError('No changes selected for import.')
        
        self.state = 'importing'
        
        BreakingChange = self.env['ai.breaking.change']
        imported = 0
        skipped = 0
        log_lines = []
        
        # Calculate from_version (one major version before to_version)
        to_major = int(self.to_version.split('.')[0])
        from_version = f"{to_major - 1}.0"
        
        for line in selected:
            # Check for duplicate
            domain = [
                ('from_version', '=', from_version),
                ('to_version', '=', self.to_version),
                ('category', '=', line.category),
                ('model_name', '=', line.model_name),
            ]
            if line.field_name:
                domain.append(('field_name', '=', line.field_name))
            if line.method_name:
                domain.append(('method_name', '=', line.method_name))
            
            existing = BreakingChange.search(domain, limit=1)
            if existing:
                skipped += 1
                log_lines.append(f"SKIP (exists): {line.description[:50]}")
                continue
            
            try:
                BreakingChange.create({
                    'from_version': from_version,
                    'to_version': self.to_version,
                    'category': line.category,
                    'model_name': line.model_name,
                    'field_name': line.field_name,
                    'method_name': line.method_name,
                    'description': line.description,
                    'old_code': line.old_code,
                    'new_code': line.new_code,
                    'source': 'community',
                    'verified': True,
                })
                imported += 1
                log_lines.append(f"OK: {line.description[:50]}")
            except Exception as e:
                skipped += 1
                log_lines.append(f"ERROR: {line.description[:30]} - {e}")
        
        self.write({
            'state': 'done',
            'imported_count': imported,
            'skipped_count': skipped,
            'import_log': '\n'.join(log_lines[-100:]),  # Last 100 lines
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Complete',
                'message': f"Imported {imported} breaking changes ({skipped} skipped)",
                'type': 'success',
            }
        }

    def action_import_from_github_clone(self):
        """Import all analysis files from a local OpenUpgrade clone."""
        self.ensure_one()
        
        if not self.github_path:
            raise UserError('Please provide the path to your local OpenUpgrade clone.')
        
        import os
        from pathlib import Path
        
        base_path = Path(self.github_path)
        if not base_path.exists():
            raise UserError(f'Path not found: {self.github_path}')
        
        # Find analysis files
        # New structure (14.0+): openupgrade_scripts/scripts/{module}/{version}/
        # Old structure: addons/{module}/migrations/{version}/
        
        analysis_files = []
        
        # New structure
        scripts_path = base_path / 'openupgrade_scripts' / 'scripts'
        if scripts_path.exists():
            for analysis_file in scripts_path.rglob('*analysis*.txt'):
                analysis_files.append(analysis_file)
        
        # Old structure
        addons_path = base_path / 'addons'
        if addons_path.exists():
            for analysis_file in addons_path.rglob('*analysis*.txt'):
                analysis_files.append(analysis_file)
        
        if not analysis_files:
            raise UserError(f'No analysis files found in {self.github_path}')
        
        # Combine all analysis text
        combined_text = []
        for f in analysis_files:
            try:
                with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
                    content = fp.read()
                    # Add module context from path
                    module = f.parent.parent.name if 'scripts' in str(f) else f.parent.parent.parent.name
                    combined_text.append(f"# Module: {module}\n{content}")
            except Exception as e:
                _logger.warning(f"Could not read {f}: {e}")
        
        self.analysis_text = '\n\n'.join(combined_text)
        self.source_type = 'text'
        
        return self.action_parse_preview()

    def _get_analysis_text(self):
        """Get analysis text from the selected source."""
        if self.source_type == 'file' and self.file_data:
            return base64.b64decode(self.file_data).decode('utf-8', errors='ignore')
        elif self.source_type == 'text' and self.analysis_text:
            return self.analysis_text
        elif self.source_type == 'github' and self.github_path:
            # Will be handled by action_import_from_github_clone
            return None
        return None


class OpenUpgradeImporterLine(models.TransientModel):
    """Preview line for OpenUpgrade import."""
    _name = 'ai.openupgrade.importer.line'
    _description = 'OpenUpgrade Import Preview Line'

    importer_id = fields.Many2one('ai.openupgrade.importer', ondelete='cascade')
    selected = fields.Boolean('Import', default=True)
    
    category = fields.Selection([
        ('field_rename', 'Field Renamed'),
        ('field_remove', 'Field Removed'),
        ('field_type', 'Field Type Changed'),
        ('field_new', 'Field Added'),
        ('method_rename', 'Method Renamed'),
        ('method_remove', 'Method Removed'),
        ('method_signature', 'Method Signature'),
        ('view_change', 'View Changed'),
        ('xmlid_change', 'XML ID Changed'),
        ('model_rename', 'Model Renamed'),
        ('behavior', 'Behavior Changed'),
        ('other', 'Other'),
    ])
    
    module = fields.Char('Module')
    model_name = fields.Char('Model')
    field_name = fields.Char('Field')
    method_name = fields.Char('Method')
    change_type = fields.Char('Change Type')
    description = fields.Text('Description')
    old_code = fields.Text('Old')
    new_code = fields.Text('New')


class OpenUpgradeParser:
    """
    Parser for OpenUpgrade analysis files.
    
    Format examples:
        # Fields
        sale / sale.order / amount_total (monetary): DEL
        sale / sale.order / tax_totals (text): NEW 
        sale / sale.order / state (selection): selection_keys changed from [...] to [...]
        account / account.move / narration (html): type is now 'text'
        
        # Methods (less common in analysis files)
        account / account.move / post: DEL (renamed to action_post)
        
        # XML IDs
        DEL ir.ui.view: sale.sale_order_form
        NEW ir.model.access: account.access_account_move_user
        
        # Model info
        sale / sale.order / _inherits: DEL account.invoice
    """
    
    def __init__(self, to_version):
        self.to_version = to_version
        self.from_version = f"{int(to_version.split('.')[0]) - 1}.0"
    
    def parse(self, text):
        """Parse analysis text and return list of changes."""
        changes = []
        current_module = None
        
        for line in text.split('\n'):
            line = line.strip()
            
            if not line or line.startswith('#'):
                # Check for module marker
                if '# Module:' in line:
                    current_module = line.split('# Module:')[1].strip()
                continue
            
            # Try to parse the line
            change = self._parse_line(line, current_module)
            if change:
                changes.append(change)
        
        return changes
    
    def _parse_line(self, line, current_module=None):
        """Parse a single line from the analysis file."""
        
        # Pattern 1: Field changes
        # module / model / field (type): CHANGE_TYPE details
        field_pattern = r'^(\w+)\s*/\s*([\w.]+)\s*/\s*(\w+)\s*\((\w+)\)\s*:\s*(.+)$'
        match = re.match(field_pattern, line)
        if match:
            module, model, field, field_type, change_info = match.groups()
            return self._parse_field_change(module, model, field, field_type, change_info)
        
        # Pattern 2: Model-level changes (no field)
        # module / model / _attribute: change
        model_pattern = r'^(\w+)\s*/\s*([\w.]+)\s*/\s*(_\w+)\s*:\s*(.+)$'
        match = re.match(model_pattern, line)
        if match:
            module, model, attr, change_info = match.groups()
            return self._parse_model_change(module, model, attr, change_info)
        
        # Pattern 3: XML ID changes
        # DEL ir.ui.view: module.xmlid
        # NEW ir.model.access: module.xmlid
        xmlid_pattern = r'^(DEL|NEW)\s+([\w.]+)\s*:\s*([\w.]+)$'
        match = re.match(xmlid_pattern, line)
        if match:
            action, record_type, xmlid = match.groups()
            return self._parse_xmlid_change(action, record_type, xmlid, current_module)
        
        # Pattern 4: Simple field notation (alternative format)
        # module / model / field: CHANGE
        simple_pattern = r'^(\w+)\s*/\s*([\w.]+)\s*/\s*(\w+)\s*:\s*(.+)$'
        match = re.match(simple_pattern, line)
        if match:
            module, model, field, change_info = match.groups()
            return self._parse_simple_change(module, model, field, change_info)
        
        # Pattern 5: Model rename
        # model.old renamed to model.new
        rename_pattern = r'^([\w.]+)\s+renamed\s+to\s+([\w.]+)$'
        match = re.match(rename_pattern, line)
        if match:
            old_model, new_model = match.groups()
            return {
                'category': 'model_rename',
                'module': current_module or old_model.split('.')[0],
                'model_name': old_model,
                'field_name': None,
                'method_name': None,
                'change_type': 'renamed',
                'description': f"Model {old_model} renamed to {new_model}",
                'old_code': old_model,
                'new_code': new_model,
            }
        
        return None
    
    def _parse_field_change(self, module, model, field, field_type, change_info):
        """Parse a field change line."""
        change_info_lower = change_info.lower()
        
        # Determine category
        if 'del' in change_info_lower or change_info_lower.startswith('del'):
            category = 'field_remove'
            description = f"Field '{field}' ({field_type}) removed from {model}"
            old_code = f"record.{field}"
            new_code = "# Field no longer exists"
        elif 'new' in change_info_lower or change_info_lower.startswith('new'):
            category = 'field_new'
            description = f"Field '{field}' ({field_type}) added to {model}"
            old_code = "# Field did not exist"
            new_code = f"record.{field}"
        elif 'renamed' in change_info_lower or 'now' in change_info_lower:
            # Try to extract new name
            new_name_match = re.search(r"renamed?\s+to\s+['\"]?(\w+)['\"]?", change_info_lower)
            if new_name_match:
                new_name = new_name_match.group(1)
                category = 'field_rename'
                description = f"Field '{field}' renamed to '{new_name}' in {model}"
                old_code = f"record.{field}"
                new_code = f"record.{new_name}"
            else:
                category = 'behavior'
                description = f"Field '{field}' changed in {model}: {change_info}"
                old_code = f"# {field}: {field_type}"
                new_code = f"# {change_info}"
        elif 'type' in change_info_lower:
            # Type change
            category = 'field_type'
            new_type_match = re.search(r"type\s+(?:is\s+)?(?:now\s+)?['\"]?(\w+)['\"]?", change_info_lower)
            new_type = new_type_match.group(1) if new_type_match else 'unknown'
            description = f"Field '{field}' type changed from {field_type} to {new_type} in {model}"
            old_code = f"{field} = fields.{field_type.title()}(...)"
            new_code = f"{field} = fields.{new_type.title()}(...)"
        elif 'selection' in change_info_lower:
            category = 'behavior'
            description = f"Field '{field}' selection changed in {model}: {change_info}"
            old_code = f"# {field} selection"
            new_code = f"# {change_info}"
        else:
            category = 'behavior'
            description = f"Field '{field}' ({field_type}) in {model}: {change_info}"
            old_code = f"# {field}"
            new_code = f"# {change_info}"
        
        return {
            'category': category,
            'module': module,
            'model_name': model,
            'field_name': field,
            'method_name': None,
            'change_type': change_info[:50],
            'description': description,
            'old_code': old_code,
            'new_code': new_code,
        }
    
    def _parse_model_change(self, module, model, attr, change_info):
        """Parse model-level change (like _inherits)."""
        return {
            'category': 'behavior',
            'module': module,
            'model_name': model,
            'field_name': None,
            'method_name': None,
            'change_type': f"{attr} changed",
            'description': f"Model {model} attribute {attr}: {change_info}",
            'old_code': f"# {attr}",
            'new_code': f"# {change_info}",
        }
    
    def _parse_xmlid_change(self, action, record_type, xmlid, current_module=None):
        """Parse XML ID change (DEL/NEW views, access rules, etc.)."""
        module = xmlid.split('.')[0] if '.' in xmlid else current_module
        
        if action == 'DEL':
            if 'view' in record_type:
                category = 'view_change'
                description = f"View removed: {xmlid}"
            else:
                category = 'xmlid_change'
                description = f"Record removed: {record_type} {xmlid}"
        else:  # NEW
            category = 'xmlid_change'
            description = f"New {record_type}: {xmlid}"
        
        return {
            'category': category,
            'module': module,
            'model_name': record_type,
            'field_name': None,
            'method_name': None,
            'change_type': action,
            'description': description,
            'old_code': xmlid if action == 'DEL' else '',
            'new_code': xmlid if action == 'NEW' else '',
        }
    
    def _parse_simple_change(self, module, model, field, change_info):
        """Parse simple field change without type info."""
        change_info_lower = change_info.lower()
        
        if 'del' in change_info_lower:
            category = 'field_remove'
        elif 'new' in change_info_lower:
            category = 'field_new'
        elif 'renamed' in change_info_lower:
            category = 'field_rename'
        else:
            category = 'behavior'
        
        return {
            'category': category,
            'module': module,
            'model_name': model,
            'field_name': field,
            'method_name': None,
            'change_type': change_info[:50],
            'description': f"Field '{field}' in {model}: {change_info}",
            'old_code': f"record.{field}",
            'new_code': f"# {change_info}",
        }
