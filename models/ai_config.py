# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class QATestAIConfig(models.Model):
    _name = 'qa.test.ai.config'
    _description = 'AI Configuration for Test Generation'
    _rec_name = 'name'

    name = fields.Char(string='Configuration Name', required=True, default='Default Configuration')
    active = fields.Boolean(default=True)
    
    # AI Provider Settings
    ai_provider = fields.Selection([
        ('anthropic', 'Anthropic (Claude)'),
        ('openai', 'OpenAI (GPT)'),
    ], string='AI Provider', default='anthropic', required=True)
    
    api_key = fields.Char(string='API Key', required=True, 
                          help='API key for the selected AI provider')
    api_model = fields.Char(string='Model', default='claude-sonnet-4-20250514',
                            help='AI model to use for generation')
    api_endpoint = fields.Char(string='API Endpoint', 
                               default='https://api.anthropic.com/v1/messages',
                               help='Custom API endpoint (optional)')
    max_tokens = fields.Integer(string='Max Tokens', default=4096,
                                help='Maximum tokens for AI response')
    temperature = fields.Float(string='Temperature', default=0.3,
                               help='AI temperature (0-1). Lower = more deterministic')
    
    # Jenkins Settings
    jenkins_enabled = fields.Boolean(string='Enable Jenkins Integration', default=False)
    jenkins_url = fields.Char(string='Jenkins URL', 
                              help='e.g., http://jenkins.yourcompany.com:8080')
    jenkins_user = fields.Char(string='Jenkins Username')
    jenkins_token = fields.Char(string='Jenkins API Token')
    jenkins_job_name = fields.Char(string='Jenkins Job Name', default='odoo-robot-tests')
    
    # Test Environment Settings
    test_base_url = fields.Char(string='Test Environment URL', 
                                default='http://localhost:8069',
                                help='Odoo instance URL for running tests')
    test_db_name = fields.Char(string='Test Database', default='odoo_test')
    test_username = fields.Char(string='Test Username', default='admin')
    test_password = fields.Char(string='Test Password', default='admin')
    
    # Robot Framework Settings
    browser = fields.Selection([
        ('chrome', 'Chrome'),
        ('firefox', 'Firefox'),
        ('edge', 'Edge'),
    ], string='Browser', default='chrome')
    headless = fields.Boolean(string='Headless Mode', default=True,
                              help='Run browser in headless mode')
    timeout = fields.Integer(string='Default Timeout (seconds)', default=30)
    screenshot_on_failure = fields.Boolean(string='Screenshot on Failure', default=True)
    
    # Output Settings
    output_path = fields.Char(string='Test Output Path', 
                              default='/tmp/qa_test_generator/tests',
                              help='Path to store generated test files')
    report_path = fields.Char(string='Report Output Path',
                              default='/tmp/qa_test_generator/reports',
                              help='Path to store test reports')
    
    # Notification Settings
    notify_on_complete = fields.Boolean(string='Notify on Completion', default=True)
    notify_on_failure = fields.Boolean(string='Notify on Failure Only', default=False)
    notification_email = fields.Char(string='Notification Email',
                                     help='Email addresses (comma-separated)')
    
    company_id = fields.Many2one('res.company', string='Company', 
                                 default=lambda self: self.env.company)

    _sql_constraints = [
        ('temperature_range', 'CHECK(temperature >= 0 AND temperature <= 1)', 
         'Temperature must be between 0 and 1'),
        ('max_tokens_positive', 'CHECK(max_tokens > 0)', 
         'Max tokens must be positive'),
    ]

    @api.model
    def get_active_config(self):
        """Get the active AI configuration"""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            raise ValidationError('No active AI configuration found. Please configure AI settings.')
        return config

    def test_ai_connection(self):
        """Test connection to AI provider"""
        self.ensure_one()
        try:
            from ..services.ai_generator import AIGenerator
            generator = AIGenerator(self)
            result = generator.test_connection()
            if result:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': 'AI connection successful!',
                        'type': 'success',
                        'sticky': False,
                    }
                }
        except Exception as e:
            _logger.error(f"AI connection test failed: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Failed',
                    'message': f'Error: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def test_jenkins_connection(self):
        """Test connection to Jenkins"""
        self.ensure_one()
        if not self.jenkins_enabled:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Jenkins Disabled',
                    'message': 'Jenkins integration is not enabled.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        try:
            from ..services.jenkins_client import JenkinsClient
            client = JenkinsClient(self)
            result = client.test_connection()
            if result:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': 'Jenkins connection successful!',
                        'type': 'success',
                        'sticky': False,
                    }
                }
        except Exception as e:
            _logger.error(f"Jenkins connection test failed: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Failed',
                    'message': f'Error: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_create_output_directories(self):
        """Create output directories if they don't exist"""
        self.ensure_one()
        import os
        paths = [self.output_path, self.report_path]
        for path in paths:
            if path and not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Output directories created successfully!',
                'type': 'success',
                'sticky': False,
            }
        }
