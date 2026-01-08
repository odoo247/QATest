# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import base64
import logging
import re

_logger = logging.getLogger(__name__)


class QAGitRepository(models.Model):
    """
    Configuration for Git repository access to fetch source code.
    Supports GitHub, GitLab, Bitbucket, and custom Git servers.
    """
    _name = 'qa.git.repository'
    _description = 'Git Repository Configuration'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(default=True)
    
    # Repository Configuration
    provider = fields.Selection([
        ('github', 'GitHub'),
        ('gitlab', 'GitLab'),
        ('bitbucket', 'Bitbucket'),
        ('custom', 'Custom Git Server'),
    ], string='Provider', required=True, default='github')
    
    repo_url = fields.Char(string='Repository URL', required=True,
                           help='e.g., https://github.com/owner/repo')
    branch = fields.Char(string='Default Branch', default='main')
    
    # Authentication
    auth_type = fields.Selection([
        ('none', 'Public Repository'),
        ('token', 'Personal Access Token'),
        ('basic', 'Username/Password'),
    ], string='Authentication', default='none')
    
    access_token = fields.Char(string='Access Token')
    username = fields.Char(string='Username')
    password = fields.Char(string='Password')
    
    # API Configuration
    api_url = fields.Char(string='API URL', 
                          help='For custom Git servers. Leave empty for standard providers.')
    
    # Module Mapping
    module_path_pattern = fields.Char(
        string='Module Path Pattern',
        default='addons/{module_name}',
        help='Path pattern to find modules. Use {module_name} as placeholder.'
    )
    
    # Status
    last_sync = fields.Datetime(string='Last Sync')
    last_error = fields.Text(string='Last Error')
    
    @api.model
    def _get_api_base_url(self, provider, repo_url):
        """Get the API base URL for different providers"""
        if provider == 'github':
            # https://github.com/owner/repo -> https://api.github.com/repos/owner/repo
            match = re.match(r'https?://github\.com/([^/]+)/([^/]+)', repo_url)
            if match:
                owner, repo = match.groups()
                repo = repo.replace('.git', '')
                return f'https://api.github.com/repos/{owner}/{repo}'
        
        elif provider == 'gitlab':
            # https://gitlab.com/owner/repo -> https://gitlab.com/api/v4/projects/owner%2Frepo
            match = re.match(r'https?://([^/]+)/(.+)', repo_url)
            if match:
                host, path = match.groups()
                path = path.replace('.git', '')
                project_id = path.replace('/', '%2F')
                return f'https://{host}/api/v4/projects/{project_id}'
        
        elif provider == 'bitbucket':
            # https://bitbucket.org/owner/repo -> https://api.bitbucket.org/2.0/repositories/owner/repo
            match = re.match(r'https?://bitbucket\.org/([^/]+)/([^/]+)', repo_url)
            if match:
                owner, repo = match.groups()
                repo = repo.replace('.git', '')
                return f'https://api.bitbucket.org/2.0/repositories/{owner}/{repo}'
        
        return None
    
    def _get_headers(self):
        """Get authentication headers"""
        headers = {'Accept': 'application/json'}
        
        if self.auth_type == 'token':
            if self.provider == 'github':
                headers['Authorization'] = f'token {self.access_token}'
            elif self.provider == 'gitlab':
                headers['PRIVATE-TOKEN'] = self.access_token
            elif self.provider == 'bitbucket':
                headers['Authorization'] = f'Bearer {self.access_token}'
            else:
                headers['Authorization'] = f'Bearer {self.access_token}'
        
        return headers
    
    def _get_auth(self):
        """Get basic auth tuple if needed"""
        if self.auth_type == 'basic':
            return (self.username, self.password)
        return None
    
    def test_connection(self):
        """Test repository connection"""
        self.ensure_one()
        try:
            api_url = self._get_api_base_url(self.provider, self.repo_url)
            if not api_url:
                raise UserError(f"Could not parse repository URL: {self.repo_url}")
            
            response = requests.get(
                api_url,
                headers=self._get_headers(),
                auth=self._get_auth(),
                timeout=10
            )
            
            if response.status_code == 200:
                self.last_error = False
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': 'Repository connection successful!',
                        'type': 'success',
                    }
                }
            else:
                self.last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                raise UserError(f"Connection failed: {self.last_error}")
                
        except requests.exceptions.RequestException as e:
            self.last_error = str(e)
            raise UserError(f"Connection error: {str(e)}")
    
    def fetch_file_content(self, file_path, branch=None):
        """
        Fetch content of a single file from repository
        
        Args:
            file_path: Path to file in repository (e.g., 'addons/sale/models/sale.py')
            branch: Branch name (uses default if not specified)
        
        Returns:
            File content as string, or None if not found
        """
        self.ensure_one()
        branch = branch or self.branch
        
        try:
            api_url = self._get_api_base_url(self.provider, self.repo_url)
            
            if self.provider == 'github':
                url = f'{api_url}/contents/{file_path}?ref={branch}'
                response = requests.get(url, headers=self._get_headers(), auth=self._get_auth(), timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('encoding') == 'base64':
                        return base64.b64decode(data['content']).decode('utf-8')
                    return data.get('content', '')
            
            elif self.provider == 'gitlab':
                encoded_path = file_path.replace('/', '%2F')
                url = f'{api_url}/repository/files/{encoded_path}?ref={branch}'
                response = requests.get(url, headers=self._get_headers(), auth=self._get_auth(), timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    return base64.b64decode(data['content']).decode('utf-8')
            
            elif self.provider == 'bitbucket':
                url = f'{api_url}/src/{branch}/{file_path}'
                response = requests.get(url, headers=self._get_headers(), auth=self._get_auth(), timeout=30)
                
                if response.status_code == 200:
                    return response.text
            
            return None
            
        except Exception as e:
            _logger.warning(f"Could not fetch {file_path}: {e}")
            return None
    
    def list_directory(self, dir_path, branch=None):
        """
        List files in a directory
        
        Args:
            dir_path: Directory path in repository
            branch: Branch name
        
        Returns:
            List of file/directory info dicts
        """
        self.ensure_one()
        branch = branch or self.branch
        
        try:
            api_url = self._get_api_base_url(self.provider, self.repo_url)
            
            if self.provider == 'github':
                url = f'{api_url}/contents/{dir_path}?ref={branch}'
                response = requests.get(url, headers=self._get_headers(), auth=self._get_auth(), timeout=30)
                
                if response.status_code == 200:
                    return response.json()
            
            elif self.provider == 'gitlab':
                encoded_path = dir_path.replace('/', '%2F') if dir_path else ''
                url = f'{api_url}/repository/tree?path={encoded_path}&ref={branch}'
                response = requests.get(url, headers=self._get_headers(), auth=self._get_auth(), timeout=30)
                
                if response.status_code == 200:
                    # Convert GitLab format to common format
                    items = response.json()
                    return [{'name': item['name'], 'type': item['type'], 'path': item['path']} for item in items]
            
            elif self.provider == 'bitbucket':
                url = f'{api_url}/src/{branch}/{dir_path}'
                response = requests.get(url, headers=self._get_headers(), auth=self._get_auth(), timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get('values', [])
            
            return []
            
        except Exception as e:
            _logger.warning(f"Could not list {dir_path}: {e}")
            return []
    
    def fetch_module_files(self, module_name, branch=None):
        """
        Fetch all relevant files for an Odoo module
        
        Args:
            module_name: Technical module name
            branch: Branch name
        
        Returns:
            Dictionary with file contents:
            {
                'python_files': {'models/sale.py': 'content...', ...},
                'xml_files': {'views/sale_views.xml': 'content...', ...},
                'manifest': '__manifest__.py content'
            }
        """
        self.ensure_one()
        branch = branch or self.branch
        
        # Build module path
        module_path = self.module_path_pattern.format(module_name=module_name)
        
        result = {
            'python_files': {},
            'xml_files': {},
            'manifest': None,
            'module_path': module_path,
        }
        
        # List module directory
        files = self.list_directory(module_path, branch)
        if not files:
            _logger.warning(f"Module {module_name} not found at {module_path}")
            return result
        
        # Fetch manifest
        manifest_content = self.fetch_file_content(f'{module_path}/__manifest__.py', branch)
        if manifest_content:
            result['manifest'] = manifest_content
        
        # Fetch Python files from models directory
        models_path = f'{module_path}/models'
        model_files = self.list_directory(models_path, branch)
        for item in model_files:
            name = item.get('name', '')
            if name.endswith('.py') and not name.startswith('__'):
                file_path = f"{models_path}/{name}"
                content = self.fetch_file_content(file_path, branch)
                if content:
                    result['python_files'][f'models/{name}'] = content
        
        # Also check root level Python files
        for item in files:
            name = item.get('name', '')
            if name.endswith('.py') and name not in ['__init__.py', '__manifest__.py']:
                file_path = f"{module_path}/{name}"
                content = self.fetch_file_content(file_path, branch)
                if content:
                    result['python_files'][name] = content
        
        # Fetch XML view files
        views_path = f'{module_path}/views'
        view_files = self.list_directory(views_path, branch)
        for item in view_files:
            name = item.get('name', '')
            if name.endswith('.xml'):
                file_path = f"{views_path}/{name}"
                content = self.fetch_file_content(file_path, branch)
                if content:
                    result['xml_files'][f'views/{name}'] = content
        
        # Also check data directory for XML
        data_path = f'{module_path}/data'
        data_files = self.list_directory(data_path, branch)
        for item in data_files:
            name = item.get('name', '')
            if name.endswith('.xml'):
                file_path = f"{data_path}/{name}"
                content = self.fetch_file_content(file_path, branch)
                if content:
                    result['xml_files'][f'data/{name}'] = content
        
        self.last_sync = fields.Datetime.now()
        return result


class QAModuleSource(models.Model):
    """
    Links Odoo modules to their source code repository location.
    """
    _name = 'qa.module.source'
    _description = 'Module Source Configuration'
    _rec_name = 'module_id'

    module_id = fields.Many2one('ir.module.module', string='Module', required=True,
                                 domain=[('state', '=', 'installed')])
    module_name = fields.Char(related='module_id.name', store=True)
    
    repository_id = fields.Many2one('qa.git.repository', string='Repository', required=True)
    branch = fields.Char(string='Branch', help='Leave empty to use repository default')
    module_path = fields.Char(string='Module Path Override',
                              help='Custom path to module in repository. Leave empty to use pattern.')
    
    # Cached source code
    last_fetch = fields.Datetime(string='Last Fetched')
    source_cache = fields.Text(string='Source Cache (JSON)')
    
    _sql_constraints = [
        ('module_unique', 'unique(module_id)', 'Each module can only have one source configuration!')
    ]
    
    def fetch_source(self):
        """Fetch source code from repository"""
        self.ensure_one()
        
        module_name = self.module_id.name
        branch = self.branch or self.repository_id.branch
        
        # Override module path if specified
        if self.module_path:
            original_pattern = self.repository_id.module_path_pattern
            self.repository_id.module_path_pattern = self.module_path
        
        try:
            result = self.repository_id.fetch_module_files(module_name, branch)
            
            # Cache the result
            import json
            self.source_cache = json.dumps(result)
            self.last_fetch = fields.Datetime.now()
            
            return result
            
        finally:
            if self.module_path:
                self.repository_id.module_path_pattern = original_pattern
    
    def get_cached_source(self):
        """Get cached source or fetch if not available"""
        self.ensure_one()
        
        if self.source_cache:
            import json
            return json.loads(self.source_cache)
        
        return self.fetch_source()
