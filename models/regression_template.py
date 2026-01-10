# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class QARegressionTemplate(models.Model):
    """Pre-built regression test templates for standard Odoo modules"""
    _name = 'qa.regression.template'
    _description = 'Regression Test Template'
    _order = 'module_name, sequence'

    name = fields.Char(string='Test Name', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    
    # Module
    module_name = fields.Selection([
        ('sale', 'Sales'),
        ('purchase', 'Purchase'),
        ('stock', 'Inventory'),
        ('account', 'Accounting'),
        ('mrp', 'Manufacturing'),
        ('crm', 'CRM'),
        ('hr', 'Human Resources'),
        ('project', 'Project'),
        ('website', 'Website'),
        ('point_of_sale', 'Point of Sale'),
        ('helpdesk', 'Helpdesk'),
        ('custom', 'Custom'),
    ], string='Module', required=True)
    
    # Test details
    description = fields.Text(string='Description')
    test_type = fields.Selection([
        ('smoke', 'Smoke Test'),
        ('crud', 'CRUD Operations'),
        ('workflow', 'Workflow'),
        ('integration', 'Integration'),
        ('report', 'Report'),
    ], string='Test Type', default='workflow')
    
    # Test content
    preconditions = fields.Text(string='Preconditions')
    test_steps = fields.Text(string='Test Steps')
    expected_result = fields.Text(string='Expected Result')
    robot_code = fields.Text(string='Robot Framework Code')
    
    # Parameters that can be customized per customer
    parameter_ids = fields.One2many('qa.regression.template.param', 'template_id',
                                     string='Parameters')
    
    # Tags
    tags = fields.Char(string='Tags', help='Comma-separated tags')

    def generate_for_customer(self, customer_id):
        """Generate test case from template for a specific customer"""
        customer = self.env['qa.customer'].browse(customer_id)
        
        # Replace parameters in robot code
        robot_code = self.robot_code or ''
        for param in self.parameter_ids:
            robot_code = robot_code.replace(f'${{{param.name}}}', param.default_value or '')
        
        # Create test case
        return self.env['qa.test.case'].create({
            'name': f"{self.name} - {customer.code}",
            'description': self.description,
            'customer_id': customer_id,
            'test_type': 'regression',
            'category': self.test_type,
            'preconditions': self.preconditions,
            'expected_result': self.expected_result,
            'robot_code': robot_code,
            'template_id': self.id,
            'tags': self.tags,
        })

    @api.model
    def create_default_templates(self):
        """Create default regression test templates"""
        
        templates = [
            # ===== SALES MODULE =====
            {
                'name': 'Create and Confirm Sale Order',
                'module_name': 'sale',
                'test_type': 'workflow',
                'description': 'Verify complete sales workflow from quotation to confirmed order',
                'preconditions': '- Sales module installed\n- At least one product exists\n- At least one customer exists',
                'test_steps': '''1. Navigate to Sales > Orders > Quotations
2. Click Create
3. Select a customer
4. Add a product line
5. Click Confirm''',
                'expected_result': 'Order is confirmed with state "Sales Order" and a sequence number is generated',
                'robot_code': '''*** Test Cases ***
Test Create And Confirm Sale Order
    [Documentation]    Verify sales order workflow
    [Tags]    sales    workflow    smoke    regression
    
    Login To Odoo    ${USERNAME}    ${PASSWORD}
    Navigate To Menu    Sales    Orders    Quotations
    Click Button    Create
    Select Customer    ${TEST_CUSTOMER}
    Add Order Line    ${TEST_PRODUCT}    1
    Click Button    Confirm
    Wait Until Element Contains    xpath=//h1/span    S0
    Page Should Contain    Sales Order
''',
                'tags': 'sales,workflow,smoke',
            },
            {
                'name': 'Create Invoice from Sale Order',
                'module_name': 'sale',
                'test_type': 'workflow',
                'description': 'Verify invoicing from confirmed sale order',
                'robot_code': '''*** Test Cases ***
Test Create Invoice From Sale Order
    [Documentation]    Verify invoice creation from SO
    [Tags]    sales    invoice    regression
    
    Login To Odoo    ${USERNAME}    ${PASSWORD}
    Navigate To Sale Order    ${TEST_SO_NUMBER}
    Click Button    Create Invoice
    Click Button    Create and View Invoice
    Wait Until Page Contains    Draft
    Element Should Contain    xpath=//h1    INV/
''',
                'tags': 'sales,invoice,regression',
            },
            
            # ===== PURCHASE MODULE =====
            {
                'name': 'Create and Confirm Purchase Order',
                'module_name': 'purchase',
                'test_type': 'workflow',
                'description': 'Verify complete purchase workflow',
                'robot_code': '''*** Test Cases ***
Test Create And Confirm Purchase Order
    [Documentation]    Verify purchase order workflow
    [Tags]    purchase    workflow    smoke    regression
    
    Login To Odoo    ${USERNAME}    ${PASSWORD}
    Navigate To Menu    Purchase    Orders    Purchase Orders
    Click Button    Create
    Select Vendor    ${TEST_VENDOR}
    Add Order Line    ${TEST_PRODUCT}    10
    Click Button    Confirm Order
    Page Should Contain    Purchase Order
''',
                'tags': 'purchase,workflow,smoke',
            },
            {
                'name': 'Receive Products from PO',
                'module_name': 'purchase',
                'test_type': 'workflow',
                'description': 'Verify product receipt from purchase order',
                'robot_code': '''*** Test Cases ***
Test Receive Products From PO
    [Documentation]    Verify product receipt
    [Tags]    purchase    inventory    regression
    
    Login To Odoo    ${USERNAME}    ${PASSWORD}
    Navigate To Purchase Order    ${TEST_PO_NUMBER}
    Click Smart Button    Receipt
    Click Button    Validate
    Handle Immediate Transfer Popup
    Page Should Contain    Done
''',
                'tags': 'purchase,inventory,regression',
            },
            
            # ===== INVENTORY MODULE =====
            {
                'name': 'Create Internal Transfer',
                'module_name': 'stock',
                'test_type': 'workflow',
                'description': 'Verify internal stock transfer between locations',
                'robot_code': '''*** Test Cases ***
Test Create Internal Transfer
    [Documentation]    Verify internal transfer
    [Tags]    inventory    transfer    regression
    
    Login To Odoo    ${USERNAME}    ${PASSWORD}
    Navigate To Menu    Inventory    Operations    Transfers
    Click Button    Create
    Select Operation Type    Internal Transfer
    Add Product Line    ${TEST_PRODUCT}    5
    Click Button    Mark as To Do
    Click Button    Validate
    Page Should Contain    Done
''',
                'tags': 'inventory,transfer,regression',
            },
            {
                'name': 'Inventory Adjustment',
                'module_name': 'stock',
                'test_type': 'workflow',
                'description': 'Verify inventory adjustment / stock count',
                'robot_code': '''*** Test Cases ***
Test Inventory Adjustment
    [Documentation]    Verify inventory adjustment
    [Tags]    inventory    adjustment    regression
    
    Login To Odoo    ${USERNAME}    ${PASSWORD}
    Navigate To Menu    Inventory    Operations    Physical Inventory
    Click Button    Create
    Input Text    name    Test Adjustment
    Click Button    Start Inventory
    Set Counted Quantity    ${TEST_PRODUCT}    100
    Click Button    Validate Inventory
    Page Should Contain    Validated
''',
                'tags': 'inventory,adjustment,regression',
            },
            
            # ===== ACCOUNTING MODULE =====
            {
                'name': 'Create Customer Invoice',
                'module_name': 'account',
                'test_type': 'workflow',
                'description': 'Verify manual customer invoice creation',
                'robot_code': '''*** Test Cases ***
Test Create Customer Invoice
    [Documentation]    Verify invoice creation
    [Tags]    accounting    invoice    regression
    
    Login To Odoo    ${USERNAME}    ${PASSWORD}
    Navigate To Menu    Accounting    Customers    Invoices
    Click Button    Create
    Select Customer    ${TEST_CUSTOMER}
    Add Invoice Line    ${TEST_PRODUCT}    1    100.00
    Click Button    Confirm
    Page Should Contain    Posted
''',
                'tags': 'accounting,invoice,regression',
            },
            {
                'name': 'Register Payment',
                'module_name': 'account',
                'test_type': 'workflow',
                'description': 'Verify payment registration on invoice',
                'robot_code': '''*** Test Cases ***
Test Register Payment
    [Documentation]    Verify payment registration
    [Tags]    accounting    payment    regression
    
    Login To Odoo    ${USERNAME}    ${PASSWORD}
    Navigate To Invoice    ${TEST_INVOICE_NUMBER}
    Click Button    Register Payment
    Select Journal    Bank
    Click Button    Create Payment
    Page Should Contain    Paid
''',
                'tags': 'accounting,payment,regression',
            },
            
            # ===== CRM MODULE =====
            {
                'name': 'Create Lead and Convert to Opportunity',
                'module_name': 'crm',
                'test_type': 'workflow',
                'description': 'Verify CRM lead to opportunity conversion',
                'robot_code': '''*** Test Cases ***
Test Lead To Opportunity
    [Documentation]    Verify lead conversion
    [Tags]    crm    lead    regression
    
    Login To Odoo    ${USERNAME}    ${PASSWORD}
    Navigate To Menu    CRM    Leads
    Click Button    Create
    Input Text    name    Test Lead
    Input Text    email_from    test@example.com
    Click Button    Save
    Click Button    Convert to Opportunity
    Click Button    Create Opportunity
    Page Should Contain    Opportunity
''',
                'tags': 'crm,lead,regression',
            },
            
            # ===== DATA INTEGRITY CHECKS =====
            {
                'name': 'Check Orphan Stock Moves',
                'module_name': 'stock',
                'test_type': 'integration',
                'description': 'Verify no orphaned stock moves exist',
                'robot_code': '''*** Test Cases ***
Test No Orphan Stock Moves
    [Documentation]    Check for orphaned stock moves
    [Tags]    data_integrity    inventory    regression
    
    ${count}=    Execute SQL    
    ...    SELECT COUNT(*) FROM stock_move WHERE picking_id IS NULL AND state != 'cancel'
    Should Be Equal As Numbers    ${count}    0    Orphaned stock moves found!
''',
                'tags': 'data_integrity,inventory',
            },
            {
                'name': 'Check Account Balance',
                'module_name': 'account',
                'test_type': 'integration',
                'description': 'Verify debit/credit balance is zero',
                'robot_code': '''*** Test Cases ***
Test Account Balance
    [Documentation]    Verify accounting balance
    [Tags]    data_integrity    accounting    regression
    
    ${result}=    Execute SQL    
    ...    SELECT ABS(SUM(debit) - SUM(credit)) FROM account_move_line WHERE parent_state = 'posted'
    Should Be True    ${result} < 0.01    Accounting imbalance detected!
''',
                'tags': 'data_integrity,accounting',
            },
        ]
        
        for template_data in templates:
            existing = self.search([
                ('name', '=', template_data['name']),
                ('module_name', '=', template_data['module_name']),
            ], limit=1)
            
            if not existing:
                self.create(template_data)
        
        return True


class QARegressionTemplateParam(models.Model):
    """Parameters for regression test templates"""
    _name = 'qa.regression.template.param'
    _description = 'Regression Template Parameter'

    template_id = fields.Many2one('qa.regression.template', string='Template',
                                   required=True, ondelete='cascade')
    name = fields.Char(string='Parameter Name', required=True,
                       help='Variable name without ${} brackets')
    description = fields.Char(string='Description')
    default_value = fields.Char(string='Default Value')
    required = fields.Boolean(string='Required', default=False)


class QARegressionSuite(models.Model):
    """Customer-specific regression suite generated from templates"""
    _name = 'qa.regression.suite'
    _description = 'Regression Test Suite'
    _inherit = ['mail.thread']
    _order = 'customer_id, name'

    name = fields.Char(string='Suite Name', required=True)
    customer_id = fields.Many2one('qa.customer', string='Customer',
                                   required=True, ondelete='cascade')
    
    # Modules to test
    module_ids = fields.Many2many('ir.module.module', string='Modules to Test',
                                   domain=[('state', '=', 'installed')])
    module_names = fields.Char(string='Module Names',
                               help='Comma-separated: sale,purchase,stock')
    
    # Generated tests
    test_ids = fields.One2many('qa.test.case', 'regression_suite_id',
                                string='Test Cases')
    test_count = fields.Integer(compute='_compute_counts')
    
    # Last run
    last_run_date = fields.Datetime(string='Last Run')
    last_run_result = fields.Selection([
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    ], string='Last Result')
    pass_rate = fields.Float(string='Pass Rate')

    @api.depends('test_ids')
    def _compute_counts(self):
        for record in self:
            record.test_count = len(record.test_ids)

    def action_generate_tests(self):
        """Generate regression tests from templates"""
        self.ensure_one()
        
        # Get modules to test
        modules = []
        if self.module_names:
            modules = [m.strip() for m in self.module_names.split(',')]
        if self.module_ids:
            modules.extend(self.module_ids.mapped('name'))
        
        if not modules:
            raise UserError("Please select modules to test")
        
        # Map to template module names
        module_mapping = {
            'sale_management': 'sale',
            'purchase_stock': 'purchase',
            'stock_account': 'stock',
            'account_accountant': 'account',
        }
        
        template_modules = set()
        for m in modules:
            template_modules.add(module_mapping.get(m, m))
        
        # Get templates
        templates = self.env['qa.regression.template'].search([
            ('module_name', 'in', list(template_modules)),
            ('active', '=', True),
        ])
        
        # Generate tests
        count = 0
        for template in templates:
            test = template.generate_for_customer(self.customer_id.id)
            test.regression_suite_id = self.id
            count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Tests Generated',
                'message': f'Created {count} regression tests',
                'type': 'success',
            }
        }

    def action_view_tests(self):
        """View test cases in this regression suite"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Tests - {self.name}',
            'res_model': 'qa.test.case',
            'view_mode': 'list,form',
            'domain': [('regression_suite_id', '=', self.id)],
            'context': {'default_regression_suite_id': self.id, 'default_customer_id': self.customer_id.id},
        }

    def action_run_suite(self):
        """Run all regression tests"""
        self.ensure_one()
        if not self.test_ids:
            raise UserError("No test cases in suite")
        
        # Create test run
        run = self.env['qa.test.run'].create({
            'name': f"Regression: {self.name}",
            'customer_id': self.customer_id.id,
            'test_case_ids': [(6, 0, self.test_ids.ids)],
            'triggered_by': 'manual',
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Test Run',
            'res_model': 'qa.test.run',
            'res_id': run.id,
            'view_mode': 'form',
        }
