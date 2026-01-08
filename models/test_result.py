# -*- coding: utf-8 -*-

from odoo import models, fields, api
import base64
import logging

_logger = logging.getLogger(__name__)


class QATestResult(models.Model):
    _name = 'qa.test.result'
    _description = 'Test Result'
    _order = 'execution_date desc'

    name = fields.Char(string='Result Name', compute='_compute_name', store=True)
    
    # Relations
    test_case_id = fields.Many2one('qa.test.case', string='Test Case', 
                                   required=True, ondelete='cascade')
    run_id = fields.Many2one('qa.test.run', string='Test Run', ondelete='cascade')
    spec_id = fields.Many2one('qa.test.spec', string='Specification',
                              related='test_case_id.spec_id', store=True)
    suite_id = fields.Many2one('qa.test.suite', string='Suite',
                               related='test_case_id.suite_id', store=True)
    
    # Status
    status = fields.Selection([
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('error', 'Error'),
        ('skipped', 'Skipped'),
    ], string='Status', default='pending', required=True)
    status_icon = fields.Char(string='Status Icon', compute='_compute_status_icon')
    
    # Timing
    execution_date = fields.Datetime(string='Execution Date', default=fields.Datetime.now)
    duration = fields.Float(string='Duration (seconds)')
    duration_display = fields.Char(string='Duration', compute='_compute_duration_display')
    
    # Output
    message = fields.Text(string='Message')
    log = fields.Text(string='Execution Log')
    
    # Screenshots
    screenshot = fields.Binary(string='Screenshot')
    screenshot_name = fields.Char(string='Screenshot Filename', default='screenshot.png')
    screenshot_preview = fields.Html(string='Screenshot Preview', compute='_compute_screenshot_preview')
    
    # Error details
    error_type = fields.Char(string='Error Type')
    error_traceback = fields.Text(string='Error Traceback')
    error_line = fields.Integer(string='Error Line')
    
    # Step results (if detailed)
    step_result_ids = fields.One2many('qa.test.step.result', 'result_id', string='Step Results')
    
    # Environment info
    browser = fields.Char(string='Browser')
    browser_version = fields.Char(string='Browser Version')
    platform = fields.Char(string='Platform')
    
    # Additional data (JSON)
    extra_data = fields.Text(string='Extra Data (JSON)')

    @api.depends('test_case_id', 'status', 'execution_date')
    def _compute_name(self):
        for result in self:
            if result.test_case_id and result.execution_date:
                date_str = result.execution_date.strftime('%Y-%m-%d %H:%M')
                result.name = f"{result.test_case_id.name} - {result.status} ({date_str})"
            else:
                result.name = 'New Result'

    @api.depends('status')
    def _compute_status_icon(self):
        icon_map = {
            'pending': '⏳',
            'running': '🔄',
            'passed': '✅',
            'failed': '❌',
            'error': '⚠️',
            'skipped': '⏭️',
        }
        for result in self:
            result.status_icon = icon_map.get(result.status, '❓')

    @api.depends('duration')
    def _compute_duration_display(self):
        for result in self:
            if result.duration:
                if result.duration < 1:
                    result.duration_display = f"{int(result.duration * 1000)}ms"
                elif result.duration < 60:
                    result.duration_display = f"{result.duration:.2f}s"
                else:
                    minutes = int(result.duration // 60)
                    seconds = int(result.duration % 60)
                    result.duration_display = f"{minutes}m {seconds}s"
            else:
                result.duration_display = '-'

    @api.depends('screenshot')
    def _compute_screenshot_preview(self):
        for result in self:
            if result.screenshot:
                result.screenshot_preview = f'''
                    <div style="max-width:400px;">
                        <img src="data:image/png;base64,{result.screenshot.decode('utf-8')}" 
                             style="max-width:100%;border:1px solid #ddd;border-radius:4px;"/>
                    </div>
                '''
            else:
                result.screenshot_preview = '<p style="color:#999;">No screenshot available</p>'

    def action_view_full_log(self):
        """View full log in popup"""
        self.ensure_one()
        return {
            'name': 'Execution Log',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.result',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'view_id': self.env.ref('qa_test_generator.view_test_result_log_popup').id,
        }

    def action_view_screenshot(self):
        """View screenshot in popup"""
        self.ensure_one()
        return {
            'name': 'Screenshot',
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.result',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'view_id': self.env.ref('qa_test_generator.view_test_result_screenshot_popup').id,
        }

    def action_download_screenshot(self):
        """Download screenshot"""
        self.ensure_one()
        if not self.screenshot:
            return
        
        attachment = self.env['ir.attachment'].create({
            'name': self.screenshot_name or 'screenshot.png',
            'type': 'binary',
            'datas': self.screenshot,
            'res_model': self._name,
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_rerun_test(self):
        """Re-run the test that produced this result"""
        self.ensure_one()
        return self.test_case_id.action_run_test()

    def action_view_test_case(self):
        """View the test case"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'qa.test.case',
            'view_mode': 'form',
            'res_id': self.test_case_id.id,
        }


class QATestStepResult(models.Model):
    _name = 'qa.test.step.result'
    _description = 'Test Step Result'
    _order = 'sequence'

    result_id = fields.Many2one('qa.test.result', string='Result', 
                                required=True, ondelete='cascade')
    step_id = fields.Many2one('qa.test.step', string='Test Step')
    
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Step Name')
    
    status = fields.Selection([
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('error', 'Error'),
        ('skipped', 'Skipped'),
    ], string='Status', required=True)
    
    duration = fields.Float(string='Duration (s)')
    message = fields.Text(string='Message')
    screenshot = fields.Binary(string='Screenshot')
