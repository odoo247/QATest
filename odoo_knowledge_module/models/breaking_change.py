# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AiBreakingChange(models.Model):
    _name = 'ai.breaking.change'
    _description = 'Odoo Breaking Change'
    _order = 'from_version, to_version, model_name'

    from_version = fields.Selection([
        ('13.0', '13.0'), ('14.0', '14.0'), ('15.0', '15.0'),
        ('16.0', '16.0'), ('17.0', '17.0'), ('18.0', '18.0'), ('19.0', '19.0'),
    ], string='From Version', required=True, index=True)
    
    to_version = fields.Selection([
        ('13.0', '13.0'), ('14.0', '14.0'), ('15.0', '15.0'),
        ('16.0', '16.0'), ('17.0', '17.0'), ('18.0', '18.0'), ('19.0', '19.0'),
    ], string='To Version', required=True, index=True)
    
    category = fields.Selection([
        ('field_rename', 'Field Renamed'),
        ('field_remove', 'Field Removed'),
        ('field_type', 'Field Type Changed'),
        ('method_rename', 'Method Renamed'),
        ('method_remove', 'Method Removed'),
        ('method_signature', 'Method Signature'),
        ('view_change', 'View Changed'),
        ('js_change', 'JavaScript/OWL'),
        ('api_change', 'API Changed'),
        ('behavior', 'Behavior Changed'),
        ('other', 'Other'),
    ], string='Category', required=True, index=True)
    
    model_name = fields.Char('Model', index=True)
    field_name = fields.Char('Field')
    method_name = fields.Char('Method')
    
    description = fields.Text('Description', required=True)
    old_code = fields.Text('Old Code')
    new_code = fields.Text('New Code')
    migration_hint = fields.Text('Migration Hint')
    
    source = fields.Selection([
        ('official', 'Official'), ('community', 'Community'),
        ('learned', 'Learned'), ('manual', 'Manual'),
    ], default='manual')
    
    verified = fields.Boolean('Verified', default=False)

    def to_context(self):
        """Convert to AI context string."""
        self.ensure_one()
        lines = [f"- {self.category}: {self.description}"]
        if self.old_code and self.new_code:
            lines.append(f"  `{self.old_code}` → `{self.new_code}`")
        return '\n'.join(lines)
