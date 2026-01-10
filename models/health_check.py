# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
import json
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class QAHealthCheck(models.Model):
    """Health Check - Monitor integrations, data integrity, studio changes"""
    _name = 'qa.health.check'
    _description = 'Health Check Monitor'
    _order = 'sequence, name'

    name = fields.Char(string='Check Name', required=True)
    code = fields.Char(string='Check Code', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    
    # Customer
    customer_id = fields.Many2one('qa.customer', string='Customer',
                                   required=True, ondelete='cascade')
    server_id = fields.Many2one('qa.customer.server', string='Server',
                                 domain="[('customer_id', '=', customer_id)]")
    
    # Check Type
    check_type = fields.Selection([
        ('integration', 'Integration / API'),
        ('data_integrity', 'Data Integrity'),
        ('studio_change', 'Studio Change Detection'),
        ('cron_job', 'Scheduled Job'),
        ('performance', 'Performance'),
        ('security', 'Security'),
        ('backup', 'Backup'),
        ('custom', 'Custom Check'),
    ], string='Check Type', required=True, default='integration')
    
    # Configuration based on type
    # Integration checks
    endpoint_url = fields.Char(string='Endpoint URL')
    http_method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('HEAD', 'HEAD'),
    ], string='HTTP Method', default='GET')
    expected_status = fields.Integer(string='Expected Status', default=200)
    timeout = fields.Integer(string='Timeout (seconds)', default=30)
    auth_header = fields.Char(string='Auth Header')
    
    # Data integrity checks
    check_query = fields.Text(string='SQL Query / Domain',
                              help='SQL query or Odoo domain to check')
    expected_result = fields.Selection([
        ('zero', 'Should return 0 (no bad records)'),
        ('nonzero', 'Should return > 0'),
        ('specific', 'Should match specific value'),
    ], string='Expected Result', default='zero')
    expected_value = fields.Char(string='Expected Value')
    
    # Studio change detection
    model_to_watch = fields.Char(string='Model to Watch')
    baseline_fields = fields.Text(string='Baseline Fields (JSON)',
                                   help='Field structure snapshot')
    baseline_date = fields.Datetime(string='Baseline Date')
    
    # Cron job monitoring
    cron_id = fields.Many2one('ir.cron', string='Cron Job')
    max_age_hours = fields.Integer(string='Max Age (hours)', default=24,
                                    help='Alert if not run within this time')
    
    # Scheduling
    check_interval = fields.Selection([
        ('5min', 'Every 5 minutes'),
        ('15min', 'Every 15 minutes'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ], string='Check Interval', default='hourly')
    last_check = fields.Datetime(string='Last Check')
    next_check = fields.Datetime(string='Next Check', compute='_compute_next_check')
    
    # Results
    status = fields.Selection([
        ('unknown', 'Unknown'),
        ('ok', 'OK'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], string='Status', default='unknown')
    last_message = fields.Text(string='Last Message')
    last_value = fields.Char(string='Last Value')
    consecutive_failures = fields.Integer(string='Consecutive Failures', default=0)
    
    # History
    history_ids = fields.One2many('qa.health.check.history', 'check_id',
                                   string='History')
    
    # Alerting
    alert_on_failure = fields.Boolean(string='Alert on Failure', default=True)
    alert_email = fields.Char(string='Alert Email')
    alert_after_failures = fields.Integer(string='Alert After N Failures', default=2)

    _sql_constraints = [
        ('code_customer_unique', 'UNIQUE(code, customer_id)', 
         'Check code must be unique per customer'),
    ]

    @api.depends('check_interval', 'last_check')
    def _compute_next_check(self):
        intervals = {
            '5min': timedelta(minutes=5),
            '15min': timedelta(minutes=15),
            'hourly': timedelta(hours=1),
            'daily': timedelta(days=1),
            'weekly': timedelta(weeks=1),
        }
        for record in self:
            if record.last_check and record.check_interval:
                record.next_check = record.last_check + intervals.get(
                    record.check_interval, timedelta(hours=1))
            else:
                record.next_check = fields.Datetime.now()

    def action_view_history(self):
        """View health check history"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'History - {self.name}',
            'res_model': 'qa.health.check.history',
            'view_mode': 'list,form',
            'domain': [('health_check_id', '=', self.id)],
            'context': {'default_health_check_id': self.id},
        }

    def action_run_check(self):
        """Run this health check"""
        self.ensure_one()
        
        result = {
            'status': 'unknown',
            'message': '',
            'value': '',
        }
        
        try:
            if self.check_type == 'integration':
                result = self._check_integration()
            elif self.check_type == 'data_integrity':
                result = self._check_data_integrity()
            elif self.check_type == 'studio_change':
                result = self._check_studio_changes()
            elif self.check_type == 'cron_job':
                result = self._check_cron_job()
            elif self.check_type == 'performance':
                result = self._check_performance()
            elif self.check_type == 'custom':
                result = self._check_custom()
                
        except Exception as e:
            result = {
                'status': 'critical',
                'message': str(e),
                'value': 'ERROR',
            }
        
        # Update status
        old_status = self.status
        self.write({
            'status': result['status'],
            'last_message': result['message'],
            'last_value': result.get('value', ''),
            'last_check': fields.Datetime.now(),
            'consecutive_failures': 0 if result['status'] == 'ok' else self.consecutive_failures + 1,
        })
        
        # Create history record
        self.env['qa.health.check.history'].create({
            'check_id': self.id,
            'status': result['status'],
            'message': result['message'],
            'value': result.get('value', ''),
        })
        
        # Alert if needed
        if (result['status'] in ('warning', 'critical') and 
            self.alert_on_failure and 
            self.consecutive_failures >= self.alert_after_failures):
            self._send_alert(result)
        
        return result

    def _check_integration(self):
        """Check integration endpoint"""
        import requests
        
        url = self.endpoint_url
        if not url:
            return {'status': 'critical', 'message': 'No URL configured'}
        
        headers = {}
        if self.auth_header:
            headers['Authorization'] = self.auth_header
        
        try:
            if self.http_method == 'GET':
                response = requests.get(url, headers=headers, timeout=self.timeout)
            elif self.http_method == 'POST':
                response = requests.post(url, headers=headers, timeout=self.timeout)
            elif self.http_method == 'HEAD':
                response = requests.head(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == self.expected_status:
                return {
                    'status': 'ok',
                    'message': f'Status {response.status_code} OK',
                    'value': str(response.status_code),
                }
            else:
                return {
                    'status': 'critical',
                    'message': f'Expected {self.expected_status}, got {response.status_code}',
                    'value': str(response.status_code),
                }
                
        except requests.Timeout:
            return {'status': 'critical', 'message': f'Timeout after {self.timeout}s'}
        except requests.ConnectionError as e:
            return {'status': 'critical', 'message': f'Connection error: {str(e)}'}

    def _check_data_integrity(self):
        """Check data integrity using SQL or domain"""
        if not self.check_query:
            return {'status': 'critical', 'message': 'No query configured'}
        
        try:
            # Try as Odoo domain first
            if self.check_query.startswith('['):
                domain = eval(self.check_query)
                model_name = self.model_to_watch or 'res.partner'
                count = self.env[model_name].search_count(domain)
            else:
                # Raw SQL
                self.env.cr.execute(self.check_query)
                result = self.env.cr.fetchone()
                count = result[0] if result else 0
            
            # Evaluate result
            if self.expected_result == 'zero':
                if count == 0:
                    return {'status': 'ok', 'message': 'No issues found', 'value': '0'}
                else:
                    return {'status': 'critical', 'message': f'Found {count} problematic records', 'value': str(count)}
            elif self.expected_result == 'nonzero':
                if count > 0:
                    return {'status': 'ok', 'message': f'Found {count} records', 'value': str(count)}
                else:
                    return {'status': 'warning', 'message': 'Expected records but found none', 'value': '0'}
            elif self.expected_result == 'specific':
                if str(count) == self.expected_value:
                    return {'status': 'ok', 'message': f'Value matches: {count}', 'value': str(count)}
                else:
                    return {'status': 'critical', 'message': f'Expected {self.expected_value}, got {count}', 'value': str(count)}
                    
        except Exception as e:
            return {'status': 'critical', 'message': f'Query error: {str(e)}'}

    def _check_studio_changes(self):
        """Detect changes made via Odoo Studio"""
        if not self.model_to_watch:
            return {'status': 'critical', 'message': 'No model configured'}
        
        try:
            # Get current field structure
            model = self.env[self.model_to_watch]
            current_fields = {}
            for fname, field in model._fields.items():
                current_fields[fname] = {
                    'type': field.type,
                    'string': field.string,
                    'required': field.required,
                    'readonly': field.readonly,
                }
            
            # Compare with baseline
            if not self.baseline_fields:
                # First run - set baseline
                self.baseline_fields = json.dumps(current_fields)
                self.baseline_date = fields.Datetime.now()
                return {'status': 'ok', 'message': 'Baseline captured', 'value': f'{len(current_fields)} fields'}
            
            baseline = json.loads(self.baseline_fields)
            
            # Find differences
            added = set(current_fields.keys()) - set(baseline.keys())
            removed = set(baseline.keys()) - set(current_fields.keys())
            modified = []
            
            for fname in set(current_fields.keys()) & set(baseline.keys()):
                if current_fields[fname] != baseline[fname]:
                    modified.append(fname)
            
            if added or removed or modified:
                changes = []
                if added:
                    changes.append(f"Added: {', '.join(added)}")
                if removed:
                    changes.append(f"Removed: {', '.join(removed)}")
                if modified:
                    changes.append(f"Modified: {', '.join(modified)}")
                
                return {
                    'status': 'warning',
                    'message': '; '.join(changes),
                    'value': f'+{len(added)} -{len(removed)} ~{len(modified)}',
                }
            
            return {'status': 'ok', 'message': 'No changes detected', 'value': 'unchanged'}
            
        except Exception as e:
            return {'status': 'critical', 'message': f'Error: {str(e)}'}

    def _check_cron_job(self):
        """Check if cron job is running properly"""
        if not self.cron_id:
            return {'status': 'critical', 'message': 'No cron job configured'}
        
        cron = self.cron_id
        
        if not cron.active:
            return {'status': 'warning', 'message': 'Cron job is disabled', 'value': 'disabled'}
        
        # Check last execution
        if cron.lastcall:
            age = fields.Datetime.now() - cron.lastcall
            age_hours = age.total_seconds() / 3600
            
            if age_hours > self.max_age_hours:
                return {
                    'status': 'critical',
                    'message': f'Last run {age_hours:.1f} hours ago (max: {self.max_age_hours}h)',
                    'value': f'{age_hours:.1f}h',
                }
            else:
                return {
                    'status': 'ok',
                    'message': f'Last run {age_hours:.1f} hours ago',
                    'value': f'{age_hours:.1f}h',
                }
        
        return {'status': 'warning', 'message': 'Never executed', 'value': 'never'}

    def _check_performance(self):
        """Check system performance"""
        import time
        
        # Simple query performance test
        start = time.time()
        self.env['res.partner'].search_count([])
        elapsed = time.time() - start
        
        if elapsed < 1:
            return {'status': 'ok', 'message': f'Query time: {elapsed:.3f}s', 'value': f'{elapsed:.3f}s'}
        elif elapsed < 5:
            return {'status': 'warning', 'message': f'Slow query: {elapsed:.3f}s', 'value': f'{elapsed:.3f}s'}
        else:
            return {'status': 'critical', 'message': f'Very slow: {elapsed:.3f}s', 'value': f'{elapsed:.3f}s'}

    def _check_custom(self):
        """Run custom check code"""
        if not self.check_query:
            return {'status': 'critical', 'message': 'No custom code configured'}
        
        # Execute custom Python code
        local_vars = {'self': self, 'env': self.env}
        try:
            exec(self.check_query, {}, local_vars)
            return local_vars.get('result', {'status': 'ok', 'message': 'Check completed'})
        except Exception as e:
            return {'status': 'critical', 'message': f'Execution error: {str(e)}'}

    def _send_alert(self, result):
        """Send alert notification"""
        if not self.alert_email:
            return
        
        template = self.env.ref('qa_test_generator.mail_template_health_alert', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
        else:
            # Fallback: direct email
            self.env['mail.mail'].create({
                'subject': f'[QA Alert] {self.customer_id.code}: {self.name} - {result["status"].upper()}',
                'body_html': f"""
                    <p>Health check alert for <strong>{self.customer_id.name}</strong></p>
                    <ul>
                        <li>Check: {self.name}</li>
                        <li>Status: {result['status'].upper()}</li>
                        <li>Message: {result['message']}</li>
                        <li>Time: {fields.Datetime.now()}</li>
                    </ul>
                """,
                'email_to': self.alert_email,
            }).send()

    def action_reset_baseline(self):
        """Reset studio change baseline"""
        self.ensure_one()
        self.baseline_fields = False
        self.baseline_date = False
        return self.action_run_check()

    @api.model
    def run_scheduled_checks(self):
        """Cron job to run all due health checks"""
        now = fields.Datetime.now()
        checks = self.search([
            ('active', '=', True),
            '|',
            ('next_check', '<=', now),
            ('last_check', '=', False),
        ])
        
        for check in checks:
            try:
                check.action_run_check()
            except Exception as e:
                _logger.error(f"Health check {check.code} failed: {str(e)}")


class QAHealthCheckHistory(models.Model):
    """Health Check History"""
    _name = 'qa.health.check.history'
    _description = 'Health Check History'
    _order = 'check_time desc'

    check_id = fields.Many2one('qa.health.check', string='Health Check',
                                required=True, ondelete='cascade')
    check_time = fields.Datetime(string='Check Time', default=fields.Datetime.now)
    status = fields.Selection([
        ('unknown', 'Unknown'),
        ('ok', 'OK'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], string='Status')
    message = fields.Text(string='Message')
    value = fields.Char(string='Value')
