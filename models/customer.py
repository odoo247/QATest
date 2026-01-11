# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class QACustomer(models.Model):
    """Customer/Client for multi-tenant QA management"""
    _name = 'qa.customer'
    _description = 'QA Customer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Customer Name', required=True, tracking=True)
    code = fields.Char(string='Code', required=True, 
                       help='Short code for the customer (e.g., ACME)')
    active = fields.Boolean(default=True)
    
    # Responsible User
    user_id = fields.Many2one('res.users', string='Account Manager',
                              default=lambda self: self.env.user,
                              help='User responsible for this customer')
    
    # Contact Info
    contact_name = fields.Char(string='Contact Person')
    contact_email = fields.Char(string='Contact Email')
    contact_phone = fields.Char(string='Contact Phone')
    
    # Technical Info
    odoo_version = fields.Selection([
        ('16.0', 'Odoo 16'),
        ('17.0', 'Odoo 17'),
        ('18.0', 'Odoo 18'),
    ], string='Odoo Version', default='18.0', required=True)
    
    # Relations
    server_ids = fields.One2many('qa.customer.server', 'customer_id', 
                                  string='Servers')
    repository_ids = fields.One2many('qa.git.repository', 'customer_id',
                                     string='Git Repositories')
    spec_ids = fields.One2many('qa.test.spec', 'customer_id',
                               string='Test Specifications')
    suite_ids = fields.One2many('qa.test.suite', 'customer_id',
                                string='Test Suites')
    
    # Statistics
    server_count = fields.Integer(compute='_compute_counts')
    repository_count = fields.Integer(compute='_compute_counts')
    spec_count = fields.Integer(compute='_compute_counts')
    test_count = fields.Integer(compute='_compute_counts')
    suite_count = fields.Integer(compute='_compute_counts')
    last_run_date = fields.Datetime(compute='_compute_last_run', store=True)
    last_run_status = fields.Selection([
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('error', 'Error'),
        ('cancelled', 'Cancelled'),
    ], compute='_compute_last_run', store=True)
    pass_rate = fields.Float(compute='_compute_pass_rate', store=True)
    
    # Notes
    notes = fields.Text(string='Notes')
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Customer code must be unique'),
    ]

    @api.depends('server_ids', 'repository_ids', 'spec_ids', 'suite_ids', 'spec_ids.test_case_ids')
    def _compute_counts(self):
        for record in self:
            record.server_count = len(record.server_ids)
            record.repository_count = len(record.repository_ids)
            record.spec_count = len(record.spec_ids)
            record.suite_count = len(record.suite_ids)
            record.test_count = sum(len(spec.test_case_ids) for spec in record.spec_ids)

    @api.depends('suite_ids.run_ids')
    def _compute_last_run(self):
        for record in self:
            runs = self.env['qa.test.run'].search([
                ('suite_id', 'in', record.suite_ids.ids)
            ], order='start_time desc', limit=1)
            if runs:
                record.last_run_date = runs[0].start_time
                record.last_run_status = runs[0].state
            else:
                record.last_run_date = False
                record.last_run_status = False

    @api.depends('suite_ids.run_ids.pass_rate')
    def _compute_pass_rate(self):
        for record in self:
            runs = self.env['qa.test.run'].search([
                ('suite_id', 'in', record.suite_ids.ids),
                ('state', 'in', ['passed', 'failed'])
            ], order='start_time desc', limit=10)
            if runs:
                record.pass_rate = sum(r.pass_rate for r in runs) / len(runs)
            else:
                record.pass_rate = 0.0

    def action_view_specs(self):
        """View customer's test specifications"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - Specifications',
            'res_model': 'qa.test.spec',
            'view_mode': 'list,kanban,form',
            'domain': [('customer_id', '=', self.id)],
            'context': {'default_customer_id': self.id},
        }

    def action_view_suites(self):
        """View customer's test suites"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - Test Suites',
            'res_model': 'qa.test.suite',
            'view_mode': 'list,form',
            'domain': [('customer_id', '=', self.id)],
            'context': {'default_customer_id': self.id},
        }

    def action_view_servers(self):
        """View customer's servers"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - Servers',
            'res_model': 'qa.customer.server',
            'view_mode': 'list,form',
            'domain': [('customer_id', '=', self.id)],
            'context': {'default_customer_id': self.id},
        }

    def action_run_all_tests(self):
        """Run all test suites for this customer"""
        self.ensure_one()
        if not self.suite_ids:
            raise UserError("No test suites defined for this customer")
        
        # Get all test cases from all suites
        all_test_cases = self.env['qa.test.case'].search([
            ('customer_id', '=', self.id),
            ('state', '=', 'ready'),
        ])
        
        if not all_test_cases:
            raise UserError("No ready test cases found for this customer")
        
        # Get default server (prefer staging/uat)
        default_server_id = False
        if self.server_ids:
            servers = self.server_ids.sorted(
                lambda s: {'staging': 0, 'uat': 1, 'development': 2, 'production': 3}.get(s.environment, 4)
            )
            default_server_id = servers[0].id if servers else False
        
        # Open wizard to select server and run
        return {
            'type': 'ir.actions.act_window',
            'name': 'Run Tests',
            'res_model': 'qa.test.run.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_customer_id': self.id,
                'default_server_id': default_server_id,
                'default_test_case_ids': [(6, 0, all_test_cases.ids)],
            },
        }

    def action_scan_and_generate(self):
        """Open code scan wizard to scan repos and generate tests"""
        self.ensure_one()
        if not self.repository_ids:
            raise UserError("No Git repositories configured for this customer. "
                          "Please add a repository in Configuration > Git Repositories first.")
        
        # Create a new code scan and open it
        scan = self.env['qa.code.scan'].create({
            'customer_id': self.id,
            'repository_id': self.repository_ids[0].id,
            'branch': self.repository_ids[0].branch or 'main',
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Scan & Generate Tests',
            'res_model': 'qa.code.scan',
            'res_id': scan.id,
            'view_mode': 'form',
            'target': 'current',
        }


class QACustomerServer(models.Model):
    """Customer's Odoo server configuration"""
    _name = 'qa.customer.server'
    _description = 'Customer Odoo Server'
    _order = 'customer_id, sequence, name'

    name = fields.Char(string='Server Name', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    
    customer_id = fields.Many2one('qa.customer', string='Customer', 
                                   required=True, ondelete='cascade')
    
    # Environment
    environment = fields.Selection([
        ('development', 'Development'),
        ('staging', 'Staging'),
        ('uat', 'UAT'),
        ('production', 'Production'),
    ], string='Environment', default='staging', required=True)
    
    # Connection
    url = fields.Char(string='Odoo URL', required=True,
                      help='Base URL of Odoo instance (e.g., https://customer.odoo.com)')
    database = fields.Char(string='Database Name', required=True)
    
    # Authentication
    auth_type = fields.Selection([
        ('api_key', 'API Key'),
        ('password', 'Username/Password'),
    ], string='Auth Type', default='api_key', required=True)
    api_key = fields.Char(string='API Key')
    username = fields.Char(string='Username')
    password = fields.Char(string='Password')
    
    # SSH (for Robot Framework execution)
    ssh_enabled = fields.Boolean(string='SSH Enabled',
                                  help='Enable SSH for running Robot Framework tests')
    ssh_host = fields.Char(string='SSH Host')
    ssh_port = fields.Integer(string='SSH Port', default=22)
    ssh_user = fields.Char(string='SSH User')
    ssh_key = fields.Text(string='SSH Private Key')
    robot_path = fields.Char(string='Robot Path', default='/opt/robot',
                             help='Path on server where Robot Framework is installed')
    
    # Status
    last_test_date = fields.Datetime(string='Last Test', readonly=True)
    last_test_status = fields.Selection([
        ('passed', 'Passed'),
        ('failed', 'Failed'),
        ('error', 'Error'),
    ], string='Last Status', readonly=True)
    connection_status = fields.Selection([
        ('untested', 'Not Tested'),
        ('connected', 'Connected'),
        ('failed', 'Failed'),
    ], string='Connection', default='untested')

    def test_connection(self):
        """Test connection to Odoo server"""
        self.ensure_one()
        import requests
        import json
        
        try:
            # Step 1: Test basic connectivity
            version_url = f"{self.url}/web/webclient/version_info"
            response = requests.post(
                version_url,
                json={"jsonrpc": "2.0", "method": "call", "params": {}, "id": 1},
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code != 200:
                self.connection_status = 'failed'
                raise UserError(f"Server not reachable: HTTP {response.status_code}")
            
            version_data = response.json()
            server_version = version_data.get('result', {}).get('server_version', 'Unknown')
            
            # Step 2: Test authentication if credentials provided
            if self.auth_type == 'password' and self.username and self.password:
                auth_url = f"{self.url}/web/session/authenticate"
                auth_response = requests.post(
                    auth_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "call",
                        "params": {
                            "db": self.database,
                            "login": self.username,
                            "password": self.password,
                        },
                        "id": 2
                    },
                    headers={'Content-Type': 'application/json'},
                    timeout=15
                )
                
                if auth_response.status_code != 200:
                    self.connection_status = 'failed'
                    raise UserError(f"Authentication request failed: HTTP {auth_response.status_code}")
                
                auth_data = auth_response.json()
                
                # Check for error in response
                if auth_data.get('error'):
                    error_msg = auth_data['error'].get('data', {}).get('message', str(auth_data['error']))
                    self.connection_status = 'failed'
                    raise UserError(f"Authentication failed: {error_msg}")
                
                # Check if we got a valid uid
                result = auth_data.get('result', {})
                uid = result.get('uid')
                
                if not uid:
                    self.connection_status = 'failed'
                    raise UserError("Authentication failed: Invalid username or password")
                
                self.connection_status = 'connected'
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': f'Connected to {self.url}\nOdoo {server_version}\nDatabase: {self.database}\nUser: {self.username} (UID: {uid})',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            
            elif self.auth_type == 'api_key' and self.api_key:
                # Test API key by making a simple call
                test_url = f"{self.url}/web/session/get_session_info"
                test_response = requests.post(
                    test_url,
                    json={"jsonrpc": "2.0", "method": "call", "params": {}, "id": 3},
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {self.api_key}',
                    },
                    timeout=10
                )
                
                if test_response.status_code == 200:
                    self.connection_status = 'connected'
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Success',
                            'message': f'Connected to {self.url}\nOdoo {server_version}\nAPI Key validated',
                            'type': 'success',
                        }
                    }
                else:
                    self.connection_status = 'failed'
                    raise UserError("API key validation failed")
            
            else:
                # No credentials, just test connectivity
                self.connection_status = 'connected'
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Partial Success',
                        'message': f'Server reachable: {self.url}\nOdoo {server_version}\n\nNote: No credentials configured for authentication test.',
                        'type': 'warning',
                    }
                }
                
        except requests.exceptions.Timeout:
            self.connection_status = 'failed'
            raise UserError(f"Connection timed out: {self.url}")
        except requests.exceptions.ConnectionError as e:
            self.connection_status = 'failed'
            raise UserError(f"Cannot connect to server: {self.url}\n\nError: {str(e)}")
        except UserError:
            raise
        except Exception as e:
            self.connection_status = 'failed'
            raise UserError(f"Connection failed: {str(e)}")

    def action_view_runs(self):
        """View test runs on this server"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.name} - Test Runs',
            'res_model': 'qa.test.run',
            'view_mode': 'list,form',
            'domain': [('server_id', '=', self.id)],
            'context': {'default_server_id': self.id},
        }
