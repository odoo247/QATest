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
