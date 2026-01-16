# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json

class AiKnowledgeAPI(http.Controller):
    
    def _json(self, data, status=200):
        return request.make_response(json.dumps(data), 
            headers=[('Content-Type', 'application/json')], status=status)

    @http.route('/api/ai/context/upgrade', type='http', auth='user', methods=['GET'], csrf=False)
    def upgrade_context(self, from_version=None, to_version=None, models=None, **kw):
        if not from_version or not to_version:
            return self._json({'error': 'from_version and to_version required'}, 400)
        models_list = models.split(',') if models else None
        ctx = request.env['ai.knowledge.service'].get_upgrade_context(from_version, to_version, models_list)
        return self._json({'context': ctx})

    @http.route('/api/ai/context/enhancement', type='http', auth='user', methods=['GET'], csrf=False)
    def enhancement_context(self, version='19.0', models=None, **kw):
        models_list = models.split(',') if models else None
        ctx = request.env['ai.knowledge.service'].get_enhancement_context(version, models_list)
        return self._json({'context': ctx})

    @http.route('/api/ai/context/test', type='http', auth='user', methods=['GET'], csrf=False)
    def test_context(self, version='19.0', models=None, test_type='robot', **kw):
        models_list = models.split(',') if models else None
        ctx = request.env['ai.knowledge.service'].get_test_context(version, models_list, test_type)
        return self._json({'context': ctx})

    @http.route('/api/ai/context/consultant', type='http', auth='user', methods=['GET'], csrf=False)
    def consultant_context(self, requirement=None, version='19.0', **kw):
        if not requirement:
            return self._json({'error': 'requirement required'}, 400)
        ctx = request.env['ai.knowledge.service'].get_consultant_context(requirement, version)
        return self._json({'context': ctx})

    @http.route('/api/ai/check', type='http', auth='user', methods=['GET'], csrf=False)
    def quick_check(self, requirement=None, **kw):
        if not requirement:
            return self._json({'error': 'requirement required'}, 400)
        result = request.env['ai.knowledge.service'].quick_check(requirement)
        return self._json(result)

    @http.route('/api/ai/error', type='json', auth='user', methods=['POST'], csrf=False)
    def record_error(self, **kw):
        svc = request.env['ai.knowledge.service']
        error = svc.record_error(kw['version'], kw['task_type'], kw['error_text'], 
                                 kw['wrong_code'], kw.get('model'))
        return {'success': True, 'error_id': error.id}

    @http.route('/api/ai/fix', type='json', auth='user', methods=['POST'], csrf=False)
    def record_fix(self, **kw):
        success = request.env['ai.knowledge.service'].record_fix(
            kw['error_id'], kw['correct_code'], kw.get('explanation'))
        return {'success': success}
