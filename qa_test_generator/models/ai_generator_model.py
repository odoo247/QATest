# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class QAAIGenerator(models.AbstractModel):
    """Abstract model wrapper for AI Generator service"""
    _name = 'qa.ai.generator'
    _description = 'AI Generator Service'

    @api.model
    def _get_ai_config(self):
        """Get active AI configuration"""
        return self.env['qa.test.ai.config'].search([
            ('active', '=', True)
        ], limit=1)

    @api.model
    def _get_generator(self):
        """Get AIGenerator instance"""
        from ..services.ai_generator import AIGenerator
        
        config = self._get_ai_config()
        if not config:
            raise Exception("No AI configuration found. Please configure AI settings first.")
        
        return AIGenerator(config)

    @api.model
    def generate_test_scenarios_from_code(self, model_analysis,
                                           include_crud=True,
                                           include_validation=True,
                                           include_workflow=True,
                                           include_security=True,
                                           include_negative=True,
                                           max_tests=25):
        """
        Generate test scenarios from code analysis
        
        Args:
            model_analysis: qa.model.analysis record
            include_*: Flags to include different test categories
            max_tests: Maximum number of tests to generate
        
        Returns:
            List of test scenario dictionaries
        """
        generator = self._get_generator()
        return generator.generate_test_scenarios_from_code(
            model_analysis,
            include_crud=include_crud,
            include_validation=include_validation,
            include_workflow=include_workflow,
            include_security=include_security,
            include_negative=include_negative,
            max_tests=max_tests,
        )

    @api.model
    def generate_tests(self, context):
        """Generate tests from specification context"""
        generator = self._get_generator()
        return generator.generate_tests(context)

    @api.model
    def test_connection(self):
        """Test AI connection"""
        generator = self._get_generator()
        return generator.test_connection()
