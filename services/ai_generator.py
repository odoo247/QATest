# -*- coding: utf-8 -*-

import json
import logging
import re
from typing import Dict, List, Any, Optional

_logger = logging.getLogger(__name__)


class AIGenerator:
    """Service for generating Robot Framework tests using AI (Claude)"""
    
    def __init__(self, config):
        """
        Initialize AI Generator with configuration
        
        Args:
            config: qa.test.ai.config record
        """
        self.config = config
        self.api_key = config.api_key
        self.model = config.api_model
        self.endpoint = config.api_endpoint
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
    
    def test_connection(self) -> bool:
        """Test connection to AI provider"""
        try:
            response = self._call_api("Say 'Connection successful!' in exactly those words.")
            return 'successful' in response.lower()
        except Exception as e:
            _logger.error(f"AI connection test failed: {str(e)}")
            raise
    
    def generate_tests(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate Robot Framework tests from specification
        
        Args:
            context: Dictionary containing:
                - spec_name: Name of the specification
                - specification: The functional spec text
                - preconditions: Test preconditions
                - postconditions: Expected results
                - module_name: Odoo module name
                - analyzed_models: Model information
                - analyzed_views: View information
                - analyzed_fields: Field information
                - analyzed_buttons: Button information
        
        Returns:
            Dictionary with:
                - success: bool
                - test_cases: List of generated test cases
                - log: Generation log
                - error: Error message if failed
        """
        prompt = self._build_generation_prompt(context)
        
        try:
            _logger.info(f"Generating tests for: {context.get('spec_name')}")
            response = self._call_api(prompt)
            
            # Parse the response to extract test cases
            test_cases = self._parse_response(response)
            
            return {
                'success': True,
                'test_cases': test_cases,
                'log': f"Generated {len(test_cases)} test cases\n\nAI Response:\n{response[:1000]}...",
            }
            
        except Exception as e:
            _logger.error(f"Test generation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'log': f"Generation failed: {str(e)}",
            }
    
    def _build_generation_prompt(self, context: Dict[str, Any]) -> str:
        """Build the prompt for AI test generation"""
        
        prompt = f"""You are an expert QA automation engineer specializing in Robot Framework test automation for Odoo ERP.

Your task is to generate Robot Framework test cases based on the following functional specification.

## SPECIFICATION DETAILS

**Name:** {context.get('spec_name', 'Unknown')}

**Functional Specification:**
{context.get('specification', 'No specification provided')}

**Preconditions:**
{context.get('preconditions', 'None specified')}

**Expected Results:**
{context.get('postconditions', 'None specified')}

## ODOO MODULE INFORMATION

**Module:** {context.get('module_name', 'Not specified')}

**Available Models:**
{context.get('analyzed_models', 'Not analyzed')}

**Available Views:**
{context.get('analyzed_views', 'Not analyzed')}

**Available Fields:**
{context.get('analyzed_fields', 'Not analyzed')}

**Available Buttons/Actions:**
{context.get('analyzed_buttons', 'Not analyzed')}

## REQUIREMENTS

Generate Robot Framework test cases following these guidelines:

1. **Test Structure:**
   - Use *** Settings ***, *** Variables ***, *** Test Cases ***, *** Keywords *** sections
   - Include proper documentation for each test case
   - Use meaningful test case names with TC prefix (e.g., TC001_Create_Customer_Invoice)
   - Add relevant tags (smoke, regression, critical, etc.)

2. **Odoo-Specific Best Practices:**
   - Use proper XPath locators for Odoo fields: //div[@name='field_name']//input
   - Handle Many2one fields with autocomplete: Input text, wait, click dropdown item
   - Use proper wait strategies (Wait Until Element Is Visible, Wait Until Page Contains)
   - Handle Odoo notifications and dialogs
   - Navigate using app menu icons and breadcrumbs

3. **Common Odoo Locators Pattern:**
   - Field input: //div[@name='FIELD_NAME']//input or //input[@id='FIELD_NAME']
   - Buttons: //button[@name='ACTION_NAME'] or //button[contains(text(),'Button Text')]
   - Save button: //button[contains(@class,'o_form_button_save')]
   - Create button: //button[contains(@class,'o_list_button_add')]
   - Smart buttons: //button[contains(@name,'action_view_')]
   - Status badge: //span[contains(@class,'badge') and contains(text(),'Status')]

4. **Keywords:**
   - Create reusable keywords for common operations
   - Include proper error handling
   - Add documentation to keywords

5. **Assertions:**
   - Verify expected outcomes
   - Check status changes
   - Validate field values

## OUTPUT FORMAT

Return your response in the following JSON format:

```json
{{
    "test_cases": [
        {{
            "name": "TC001_Test_Case_Name",
            "description": "Brief description of what this test does",
            "tags": "smoke, billing, invoice",
            "robot_code": "*** Test Cases ***\\nTC001_Test_Case_Name\\n    [Documentation]    Test description\\n    [Tags]    smoke    billing\\n    # Test steps here..."
        }},
        {{
            "name": "TC002_Another_Test",
            "description": "Description",
            "tags": "regression",
            "robot_code": "..."
        }}
    ]
}}
```

Generate comprehensive test cases that cover the functional specification. Include both positive and negative test scenarios where applicable.

IMPORTANT: 
- Generate ONLY valid Robot Framework syntax
- Use 4 spaces for indentation
- Include all necessary keywords inline or define them
- Make tests independent and self-contained
"""
        return prompt
    
    def _call_api(self, prompt: str) -> str:
        """Call the AI API and return the response"""
        import requests
        
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01',
        }
        
        data = {
            'model': self.model,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'messages': [
                {'role': 'user', 'content': prompt}
            ]
        }
        
        response = requests.post(
            self.endpoint,
            headers=headers,
            json=data,
            timeout=120
        )
        
        if response.status_code != 200:
            raise Exception(f"API request failed: {response.status_code} - {response.text}")
        
        result = response.json()
        
        # Extract text from Claude response
        if 'content' in result and len(result['content']) > 0:
            return result['content'][0].get('text', '')
        
        raise Exception("No content in API response")
    
    def _parse_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse AI response to extract test cases"""
        
        # Try to find JSON in the response
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r'\{[\s\S]*"test_cases"[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Fallback: treat entire response as a single test
                return [{
                    'name': 'TC001_Generated_Test',
                    'description': 'Auto-generated test from AI',
                    'tags': 'generated',
                    'robot_code': response,
                }]
        
        try:
            data = json.loads(json_str)
            test_cases = data.get('test_cases', [])
            
            # Validate and clean test cases
            cleaned_cases = []
            for tc in test_cases:
                if isinstance(tc, dict) and 'robot_code' in tc:
                    # Fix common issues in robot code
                    robot_code = tc['robot_code']
                    robot_code = robot_code.replace('\\n', '\n')
                    robot_code = robot_code.replace('\\t', '    ')
                    
                    cleaned_cases.append({
                        'name': tc.get('name', 'Unnamed_Test'),
                        'description': tc.get('description', ''),
                        'tags': tc.get('tags', ''),
                        'robot_code': robot_code,
                    })
            
            return cleaned_cases
            
        except json.JSONDecodeError as e:
            _logger.warning(f"Failed to parse JSON response: {e}")
            # Return response as single test case
            return [{
                'name': 'TC001_Generated_Test',
                'description': 'Auto-generated test from AI (JSON parse failed)',
                'tags': 'generated',
                'robot_code': response,
            }]
    
    def improve_test(self, test_case: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """Use AI to improve a test case based on execution error"""
        
        prompt = f"""You are an expert QA automation engineer. A Robot Framework test has failed.

**Test Case Name:** {test_case.get('name')}

**Original Robot Code:**
```robot
{test_case.get('robot_code')}
```

**Error Message:**
{error_message}

Please analyze the error and provide a corrected version of the test.
Common issues to check:
- Incorrect XPath locators
- Missing wait statements
- Wrong element interactions
- Timing issues

Return ONLY the corrected Robot Framework code, no explanation needed.
"""
        
        try:
            response = self._call_api(prompt)
            return {
                'success': True,
                'improved_code': response,
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    def generate_locator(self, field_info: Dict[str, Any]) -> str:
        """Generate optimal XPath locator for an Odoo field"""
        
        field_name = field_info.get('name')
        field_type = field_info.get('type')
        
        if field_type in ('char', 'text', 'integer', 'float', 'monetary'):
            return f"//div[@name='{field_name}']//input | //input[@id='{field_name}']"
        elif field_type == 'many2one':
            return f"//div[@name='{field_name}']//input[contains(@class,'o_input')]"
        elif field_type == 'boolean':
            return f"//div[@name='{field_name}']//input[@type='checkbox']"
        elif field_type == 'selection':
            return f"//div[@name='{field_name}']//select | //div[@name='{field_name}']//input"
        elif field_type == 'date':
            return f"//div[@name='{field_name}']//input[contains(@class,'o_datepicker')]"
        else:
            return f"//div[@name='{field_name}']//input | //*[@name='{field_name}']"

    def generate_test_scenarios_from_code(self, model_analysis, 
                                           include_crud=True,
                                           include_validation=True,
                                           include_workflow=True,
                                           include_security=True,
                                           include_negative=True,
                                           max_tests=25) -> List[Dict[str, Any]]:
        """
        Generate test scenarios from code analysis
        
        Args:
            model_analysis: qa.model.analysis record
            include_*: Flags to include different test categories
            max_tests: Maximum number of tests to generate
        
        Returns:
            List of test scenario dictionaries
        """
        # Parse the analysis JSON
        try:
            analysis_data = json.loads(model_analysis.analysis_json)
        except:
            analysis_data = {}
        
        prompt = self._build_code_analysis_prompt(
            model_analysis,
            analysis_data,
            include_crud,
            include_validation,
            include_workflow,
            include_security,
            include_negative,
            max_tests
        )
        
        try:
            _logger.info(f"Generating tests from code for: {model_analysis.model_name}")
            response = self._call_api(prompt)
            
            # Parse the response
            scenarios = self._parse_code_test_response(response, model_analysis.model_name)
            
            return scenarios[:max_tests]
            
        except Exception as e:
            _logger.error(f"Code-based test generation failed: {str(e)}")
            # Return basic CRUD tests as fallback
            return self._generate_fallback_tests(model_analysis, analysis_data)

    def _build_code_analysis_prompt(self, model_analysis, analysis_data,
                                     include_crud, include_validation,
                                     include_workflow, include_security,
                                     include_negative, max_tests) -> str:
        """Build prompt for code-based test generation"""
        
        # Format fields info
        fields_info = ""
        for field in analysis_data.get('fields', []):
            fields_info += f"  - {field['name']}: {field['type']}"
            if field.get('required'):
                fields_info += " (REQUIRED)"
            if field.get('compute'):
                fields_info += f" (computed: {field['compute']})"
            if field.get('selection'):
                fields_info += f" (options: {field['selection']})"
            fields_info += "\n"
        
        # Format methods info
        methods_info = ""
        for method in analysis_data.get('methods', []):
            if not method.get('is_private') or method.get('is_compute'):
                methods_info += f"  - {method['name']}()"
                if method.get('is_action'):
                    methods_info += " [BUTTON/ACTION]"
                if method.get('is_compute'):
                    methods_info += f" [COMPUTE: {method.get('depends_fields', [])}]"
                if method.get('is_onchange'):
                    methods_info += f" [ONCHANGE: {method.get('onchange_fields', [])}]"
                if method.get('is_constraint'):
                    methods_info += " [CONSTRAINT]"
                methods_info += "\n"
        
        # Format constraints
        constraints_info = ""
        for c in analysis_data.get('constraints', []):
            constraints_info += f"  - {c['name']}: validates {c.get('fields', [])}\n"
        for c in analysis_data.get('sql_constraints', []):
            constraints_info += f"  - SQL: {c['name']} - {c.get('message', '')}\n"
        
        # Format workflow
        workflow_info = ""
        if analysis_data.get('has_workflow'):
            states = analysis_data.get('states', [])
            workflow_info = f"States: {' → '.join(states)}\n"
        
        # Build test categories to include
        categories = []
        if include_crud:
            categories.append("CRUD (Create, Read, Update, Delete)")
        if include_validation:
            categories.append("Validation (required fields, constraints)")
        if include_workflow:
            categories.append("Workflow (state transitions)")
        if include_security:
            categories.append("Security (access rights)")
        if include_negative:
            categories.append("Negative tests (error handling)")
        
        prompt = f"""You are an expert QA automation engineer. Generate Robot Framework test cases based on this Odoo model analysis.

## MODEL INFORMATION

**Model:** {model_analysis.model_name}
**Description:** {model_analysis.model_description or 'N/A'}
**Inherits:** {model_analysis.inherit_model or 'N/A'}

**Fields:**
{fields_info or '  No fields found'}

**Methods:**
{methods_info or '  No public methods found'}

**Constraints:**
{constraints_info or '  No constraints found'}

**Workflow:**
{workflow_info or '  No workflow (no state field)'}

## TEST CATEGORIES TO GENERATE

{chr(10).join(f'- {c}' for c in categories)}

## REQUIREMENTS

Generate up to {max_tests} Robot Framework test cases following these guidelines:

1. **Naming Convention:** test_{{action}}_{{model}}_{{scenario}}
   Example: test_create_sale_order_with_required_fields

2. **Use Odoo XML-RPC/API testing approach:**
   - Create records using Odoo model methods
   - Validate field values and computations
   - Test constraints and error handling
   - Verify workflow transitions

3. **Test Structure:**
   - Each test should be independent
   - Include setup and assertions
   - Handle cleanup if needed

4. **For CRUD tests:**
   - Test create with minimum required fields
   - Test create with all fields
   - Test update operations
   - Test delete/archive operations

5. **For Validation tests:**
   - Test each required field (should fail without)
   - Test each constraint (should fail when violated)
   - Test field type validation

6. **For Workflow tests:**
   - Test each valid state transition
   - Test action methods that change state
   - Test invalid transitions (should fail)

7. **For Negative tests:**
   - Test with invalid data types
   - Test with missing required data
   - Test edge cases (empty, very long, special chars)

## OUTPUT FORMAT

Return your response in this JSON format:

```json
{{
    "test_scenarios": [
        {{
            "name": "test_create_model_with_required_fields",
            "test_id": "TC001",
            "description": "Verify model can be created with required fields",
            "category": "crud",
            "steps": [
                {{"name": "Create record", "action": "create", "expected": "Record created successfully"}},
                {{"name": "Verify name", "action": "assert field", "expected": "Name is set"}}
            ],
            "robot_code": "*** Test Cases ***\\nTest Create Model With Required Fields\\n    [Documentation]    Verify model creation\\n    [Tags]    crud    smoke\\n    ${{record}}=    Create Record    model.name\\n    ...    name=Test Record\\n    Should Not Be Empty    ${{record}}"
        }}
    ]
}}
```

Generate comprehensive tests covering the specified categories. Focus on testing actual business logic discovered in the code analysis.
"""
        return prompt

    def _parse_code_test_response(self, response: str, model_name: str) -> List[Dict[str, Any]]:
        """Parse AI response for code-based test generation"""
        
        # Try to find JSON in the response
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r'\{[\s\S]*"test_scenarios"[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group(0)
            else:
                _logger.warning("No JSON found in code test response")
                return []
        
        try:
            data = json.loads(json_str)
            scenarios = data.get('test_scenarios', [])
            
            # Clean up scenarios
            cleaned = []
            for i, sc in enumerate(scenarios, 1):
                if isinstance(sc, dict):
                    robot_code = sc.get('robot_code', '')
                    robot_code = robot_code.replace('\\n', '\n')
                    robot_code = robot_code.replace('\\t', '    ')
                    
                    cleaned.append({
                        'name': sc.get('name', f'test_{model_name.replace(".", "_")}_{i}'),
                        'test_id': sc.get('test_id', f'TC{i:03d}'),
                        'description': sc.get('description', ''),
                        'category': sc.get('category', 'functional'),
                        'steps': sc.get('steps', []),
                        'robot_code': robot_code,
                    })
            
            return cleaned
            
        except json.JSONDecodeError as e:
            _logger.warning(f"Failed to parse code test JSON: {e}")
            return []

    def _generate_fallback_tests(self, model_analysis, analysis_data) -> List[Dict[str, Any]]:
        """Generate basic fallback tests when AI fails"""
        
        model_name = model_analysis.model_name
        model_var = model_name.replace('.', '_')
        
        tests = []
        
        # Basic CRUD test
        tests.append({
            'name': f'test_create_{model_var}_basic',
            'test_id': 'TC001',
            'description': f'Basic create test for {model_name}',
            'category': 'crud',
            'steps': [
                {'name': 'Create record', 'action': 'create', 'expected': 'Record created'},
            ],
            'robot_code': f'''*** Test Cases ***
Test Create {model_name.replace('.', ' ').title()} Basic
    [Documentation]    Verify basic record creation for {model_name}
    [Tags]    crud    smoke    generated
    
    # Create a basic record
    ${{record}}=    Create Record    {model_name}
    ...    name=Test Record
    
    # Verify creation
    Should Not Be Empty    ${{record}}
    Log    Created record: ${{record}}
''',
        })
        
        # Required fields test
        required_fields = [f['name'] for f in analysis_data.get('fields', []) if f.get('required')]
        if required_fields:
            tests.append({
                'name': f'test_create_{model_var}_required_fields',
                'test_id': 'TC002',
                'description': f'Test required fields for {model_name}',
                'category': 'validation',
                'steps': [
                    {'name': 'Create without required', 'action': 'create', 'expected': 'Should fail'},
                ],
                'robot_code': f'''*** Test Cases ***
Test Create {model_name.replace('.', ' ').title()} Without Required Fields
    [Documentation]    Verify {model_name} requires: {', '.join(required_fields)}
    [Tags]    validation    negative    generated
    
    # Attempt to create without required fields should fail
    Run Keyword And Expect Error    *
    ...    Create Record    {model_name}
''',
            })
        
        # Workflow test
        if analysis_data.get('has_workflow'):
            states = analysis_data.get('states', ['draft'])
            tests.append({
                'name': f'test_{model_var}_workflow',
                'test_id': 'TC003',
                'description': f'Test workflow for {model_name}',
                'category': 'workflow',
                'steps': [
                    {'name': 'Check initial state', 'action': 'verify', 'expected': f'State is {states[0]}'},
                ],
                'robot_code': f'''*** Test Cases ***
Test {model_name.replace('.', ' ').title()} Workflow
    [Documentation]    Verify workflow states: {' -> '.join(states)}
    [Tags]    workflow    generated
    
    # Create record
    ${{record}}=    Create Record    {model_name}
    ...    name=Workflow Test
    
    # Verify initial state
    ${{state}}=    Get Field Value    ${{record}}    state
    Should Be Equal    ${{state}}    {states[0]}
''',
            })
        
        return tests
