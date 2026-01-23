import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class MigrationLog(models.Model):
    _name = 'migration.log'
    _description = 'Migration Log Entry'
    _order = 'create_date desc'

    project_id = fields.Many2one(
        'migration.project',
        string='Migration Project',
        required=True,
        ondelete='cascade',
        index=True,
    )
    
    action_type = fields.Selection([
        ('info', 'Information'),
        ('validate', 'Validation'),
        ('validation_error', 'Validation Error'),
        ('import_start', 'Import Started'),
        ('batch_import', 'Batch Import'),
        ('create', 'Record Created'),
        ('update', 'Record Updated'),
        ('skip', 'Record Skipped'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('import_complete', 'Import Completed'),
        ('import_error', 'Import Failed'),
        ('rollback', 'Rollback'),
    ], string='Action Type', required=True, index=True)
    
    message = fields.Text(string='Message')
    
    # Row information
    row_number = fields.Integer(string='Row Number')
    row_data = fields.Text(string='Row Data')
    
    # Record information
    record_model = fields.Char(string='Record Model')
    record_id = fields.Integer(string='Record ID')
    
    # Timing
    duration = fields.Float(string='Duration (seconds)')
    
    # User
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.uid,
    )
    
    # Display helpers
    log_level = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('success', 'Success'),
    ], string='Level', compute='_compute_log_level', store=True)
    
    @api.depends('action_type')
    def _compute_log_level(self):
        level_map = {
            'info': 'info',
            'validate': 'success',
            'validation_error': 'warning',
            'import_start': 'info',
            'batch_import': 'info',
            'create': 'success',
            'update': 'success',
            'skip': 'warning',
            'error': 'error',
            'warning': 'warning',
            'import_complete': 'success',
            'import_error': 'error',
            'rollback': 'warning',
        }
        for record in self:
            record.log_level = level_map.get(record.action_type, 'info')
    
    def action_view_record(self):
        """View the related record."""
        self.ensure_one()
        if not self.record_model or not self.record_id:
            return
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.record_model,
            'res_id': self.record_id,
            'view_mode': 'form',
        }
    
    @api.model
    def get_summary(self, project_id):
        """Get log summary for a project."""
        logs = self.search([('project_id', '=', project_id)])
        
        summary = {
            'total': len(logs),
            'errors': len(logs.filtered(lambda l: l.log_level == 'error')),
            'warnings': len(logs.filtered(lambda l: l.log_level == 'warning')),
            'success': len(logs.filtered(lambda l: l.log_level == 'success')),
        }
        
        return summary
    
    @api.model
    def cleanup_old_logs(self, days=30):
        """Remove logs older than specified days."""
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        old_logs = self.search([('create_date', '<', cutoff)])
        count = len(old_logs)
        old_logs.unlink()
        
        _logger.info(f"Cleaned up {count} old migration logs")
        return count
