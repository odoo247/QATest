# -*- coding: utf-8 -*-
"""
OdooLibrary - Robot Framework library for Odoo RPC operations

This library provides keywords for interacting with Odoo via JSON-RPC API.
Use this for API-based testing of Odoo modules.

Usage in Robot Framework:
    *** Settings ***
    Library    OdooLibrary    ${BASE_URL}    ${DATABASE}    ${USERNAME}    ${PASSWORD}
    
    *** Test Cases ***
    Test Create Partner
        ${partner_id}=    Create Record    res.partner    name=Test Partner
        Should Not Be Empty    ${partner_id}
"""

import json
import requests
from robot.api.deco import keyword, library
from robot.api import logger
from datetime import datetime


@library(scope='SUITE')
class OdooLibrary:
    """Robot Framework library for Odoo JSON-RPC operations"""
    
    ROBOT_LIBRARY_SCOPE = 'SUITE'
    
    def __init__(self, url=None, database=None, username=None, password=None):
        """
        Initialize OdooLibrary
        
        Args:
            url: Odoo server URL (e.g., http://localhost:8069)
            database: Database name
            username: Login username
            password: Login password
        """
        self.url = url.rstrip('/') if url else 'http://localhost:8069'
        self.database = database or 'odoo'
        self.username = username or 'admin'
        self.password = password or 'admin'
        self.uid = None
        self.session = requests.Session()
        self._request_id = 0
    
    def _get_request_id(self):
        self._request_id += 1
        return self._request_id
    
    def _json_rpc(self, endpoint, method, params):
        """Execute JSON-RPC call"""
        data = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'id': self._get_request_id(),
        }
        
        url = f"{self.url}{endpoint}"
        logger.debug(f"JSON-RPC: {url} - {method}")
        logger.debug(f"Params: {json.dumps(params, default=str)}")
        
        response = self.session.post(
            url,
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        
        result = response.json()
        
        if 'error' in result:
            error = result['error']
            message = error.get('data', {}).get('message', error.get('message', str(error)))
            raise Exception(f"Odoo RPC Error: {message}")
        
        return result.get('result')
    
    def _call(self, model, method, args=None, kwargs=None):
        """Call Odoo model method"""
        if not self.uid:
            self.connect()
        
        return self._json_rpc('/jsonrpc', 'call', {
            'service': 'object',
            'method': 'execute_kw',
            'args': [
                self.database,
                self.uid,
                self.password,
                model,
                method,
                args or [],
                kwargs or {}
            ]
        })
    
    # ==================== Connection Keywords ====================
    
    @keyword("Connect To Odoo")
    def connect(self, url=None, database=None, username=None, password=None):
        """
        Connect to Odoo server and authenticate
        
        Args:
            url: Odoo server URL (optional, uses init value)
            database: Database name (optional)
            username: Login username (optional)
            password: Login password (optional)
        
        Returns:
            User ID if successful
        
        Example:
            Connect To Odoo    http://localhost:8069    mydb    admin    admin
        """
        if url:
            self.url = url.rstrip('/')
        if database:
            self.database = database
        if username:
            self.username = username
        if password:
            self.password = password
        
        logger.info(f"Connecting to {self.url}, database: {self.database}")
        
        self.uid = self._json_rpc('/jsonrpc', 'call', {
            'service': 'common',
            'method': 'authenticate',
            'args': [self.database, self.username, self.password, {}]
        })
        
        if not self.uid:
            raise Exception(f"Authentication failed for user {self.username}")
        
        logger.info(f"Connected as user ID: {self.uid}")
        return self.uid
    
    @keyword("Disconnect From Odoo")
    def disconnect(self):
        """Disconnect from Odoo (reset session)"""
        self.uid = None
        self.session = requests.Session()
        logger.info("Disconnected from Odoo")
    
    # ==================== CRUD Keywords ====================
    
    @keyword("Create Record")
    def create_record(self, model, **fields):
        """
        Create a new record in Odoo
        
        Args:
            model: Model name (e.g., res.partner)
            **fields: Field values as keyword arguments
        
        Returns:
            ID of created record
        
        Example:
            ${partner_id}=    Create Record    res.partner    name=Test    email=test@test.com
        """
        logger.info(f"Creating {model} with fields: {fields}")
        record_id = self._call(model, 'create', [fields])
        logger.info(f"Created {model} ID: {record_id}")
        return record_id
    
    @keyword("Read Record")
    def read_record(self, model, record_id, fields=None):
        """
        Read a record from Odoo
        
        Args:
            model: Model name
            record_id: Record ID
            fields: List of fields to read (optional, reads all if not specified)
        
        Returns:
            Dictionary with field values
        
        Example:
            ${data}=    Read Record    res.partner    ${partner_id}
            ${data}=    Read Record    res.partner    ${partner_id}    fields=['name', 'email']
        """
        record_id = int(record_id)
        kwargs = {}
        if fields:
            kwargs['fields'] = fields if isinstance(fields, list) else [fields]
        
        result = self._call(model, 'read', [[record_id]], kwargs)
        
        if result:
            return result[0]
        return {}
    
    @keyword("Update Record")
    def update_record(self, model, record_id, **fields):
        """
        Update a record in Odoo
        
        Args:
            model: Model name
            record_id: Record ID
            **fields: Field values to update
        
        Returns:
            True if successful
        
        Example:
            Update Record    res.partner    ${partner_id}    name=New Name    phone=123456
        """
        record_id = int(record_id)
        logger.info(f"Updating {model} ID {record_id} with: {fields}")
        result = self._call(model, 'write', [[record_id], fields])
        return result
    
    @keyword("Delete Record")
    def delete_record(self, model, record_id):
        """
        Delete a record from Odoo
        
        Args:
            model: Model name
            record_id: Record ID
        
        Returns:
            True if successful
        
        Example:
            Delete Record    res.partner    ${partner_id}
        """
        record_id = int(record_id)
        logger.info(f"Deleting {model} ID {record_id}")
        result = self._call(model, 'unlink', [[record_id]])
        return result
    
    @keyword("Search Records")
    def search_records(self, model, domain=None, limit=None, order=None):
        """
        Search for records in Odoo
        
        Args:
            model: Model name
            domain: Search domain (list of tuples)
            limit: Maximum records to return
            order: Sort order
        
        Returns:
            List of record IDs
        
        Example:
            ${ids}=    Search Records    res.partner    domain=[('is_company', '=', True)]    limit=10
        """
        if domain is None:
            domain = []
        elif isinstance(domain, str):
            domain = eval(domain)
        
        kwargs = {}
        if limit:
            kwargs['limit'] = int(limit)
        if order:
            kwargs['order'] = order
        
        result = self._call(model, 'search', [domain], kwargs)
        logger.info(f"Found {len(result)} {model} records")
        return result
    
    @keyword("Search And Read Records")
    def search_read_records(self, model, domain=None, fields=None, limit=None, order=None):
        """
        Search and read records in one call
        
        Args:
            model: Model name
            domain: Search domain
            fields: Fields to read
            limit: Maximum records
            order: Sort order
        
        Returns:
            List of dictionaries with field values
        
        Example:
            ${partners}=    Search And Read Records    res.partner    domain=[('is_company', '=', True)]    fields=['name', 'email']
        """
        if domain is None:
            domain = []
        elif isinstance(domain, str):
            domain = eval(domain)
        
        kwargs = {}
        if fields:
            kwargs['fields'] = fields if isinstance(fields, list) else [fields]
        if limit:
            kwargs['limit'] = int(limit)
        if order:
            kwargs['order'] = order
        
        return self._call(model, 'search_read', [domain], kwargs)
    
    @keyword("Record Exists")
    def record_exists(self, model, record_id):
        """
        Check if a record exists
        
        Args:
            model: Model name
            record_id: Record ID
        
        Returns:
            True if exists, False otherwise
        
        Example:
            ${exists}=    Record Exists    res.partner    ${partner_id}
        """
        record_id = int(record_id)
        result = self._call(model, 'search', [[('id', '=', record_id)]])
        return len(result) > 0
    
    @keyword("Get Field Value")
    def get_field_value(self, model, record_id, field_name):
        """
        Get a single field value from a record
        
        Args:
            model: Model name
            record_id: Record ID
            field_name: Field name
        
        Returns:
            Field value
        
        Example:
            ${name}=    Get Field Value    res.partner    ${partner_id}    name
        """
        data = self.read_record(model, record_id, fields=[field_name])
        return data.get(field_name)
    
    # ==================== Method Keywords ====================
    
    @keyword("Call Method")
    def call_method(self, model, record_id, method_name, *args, **kwargs):
        """
        Call a method on a record
        
        Args:
            model: Model name
            record_id: Record ID (or list of IDs)
            method_name: Method name to call
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Method result
        
        Example:
            Call Method    account.move    ${invoice_id}    action_post
        """
        if isinstance(record_id, (int, str)):
            record_ids = [int(record_id)]
        else:
            record_ids = [int(r) for r in record_id]
        
        logger.info(f"Calling {model}.{method_name} on IDs {record_ids}")
        
        # Build the call
        return self._json_rpc('/jsonrpc', 'call', {
            'service': 'object',
            'method': 'execute_kw',
            'args': [
                self.database,
                self.uid,
                self.password,
                model,
                method_name,
                [record_ids] + list(args),
                kwargs
            ]
        })
    
    # ==================== Utility Keywords ====================
    
    @keyword("Get Current Date")
    def get_current_date(self, format='%Y-%m-%d'):
        """
        Get current date as string
        
        Args:
            format: Date format (default: %Y-%m-%d)
        
        Returns:
            Date string
        """
        return datetime.now().strftime(format)
    
    @keyword("Get Current Datetime")
    def get_current_datetime(self, format='%Y-%m-%d %H:%M:%S'):
        """
        Get current datetime as string
        
        Args:
            format: Datetime format
        
        Returns:
            Datetime string
        """
        return datetime.now().strftime(format)
    
    @keyword("Get Model Fields")
    def get_model_fields(self, model, attributes=None):
        """
        Get field definitions for a model
        
        Args:
            model: Model name (e.g., res.partner, sale.order)
            attributes: List of field attributes to return (optional)
                       Default: ['string', 'type', 'required', 'readonly']
        
        Returns:
            Dictionary mapping field names to their definitions
        
        Example:
            ${fields}=    Get Model Fields    sale.order.line
            Log    ${fields['product_id']}
        """
        self._ensure_connected()
        
        if attributes is None:
            attributes = ['string', 'type', 'required', 'readonly', 'relation']
        
        result = self._call(model, 'fields_get', [], {'attributes': attributes})
        logger.info(f"Got {len(result)} fields for model {model}")
        return result
    
    @keyword("Get Odoo Version")
    def get_odoo_version(self):
        """
        Get Odoo server version
        
        Returns:
            Version string (e.g., "17.0", "18.0", "19.0")
        
        Example:
            ${version}=    Get Odoo Version
            Log    Running on Odoo ${version}
        """
        info = self.get_server_info()
        version = info.get('server_version', 'unknown')
        logger.info(f"Odoo version: {version}")
        return version
    
    @keyword("Get Valid Fields For Create")
    def get_valid_fields_for_create(self, model):
        """
        Get list of fields that can be used when creating a record
        (excludes readonly, computed fields)
        
        Args:
            model: Model name
        
        Returns:
            Dictionary with 'required' and 'optional' field lists
        
        Example:
            ${fields}=    Get Valid Fields For Create    sale.order.line
            Log    Required: ${fields['required']}
            Log    Optional: ${fields['optional']}
        """
        all_fields = self.get_model_fields(model, ['type', 'required', 'readonly', 'string', 'relation'])
        
        required = []
        optional = []
        
        # Skip these internal/computed fields
        skip_fields = {'id', 'create_date', 'create_uid', 'write_date', 'write_uid', 
                       '__last_update', 'display_name'}
        
        for name, info in all_fields.items():
            if name in skip_fields:
                continue
            if info.get('readonly'):
                continue
            
            field_info = {
                'name': name,
                'type': info.get('type'),
                'string': info.get('string'),
                'relation': info.get('relation'),
            }
            
            if info.get('required'):
                required.append(field_info)
            else:
                optional.append(field_info)
        
        logger.info(f"Model {model}: {len(required)} required, {len(optional)} optional fields")
        return {'required': required, 'optional': optional}

    @keyword("Get Server Info")
    def get_server_info(self):
        """
        Get Odoo server information
        
        Returns:
            Dictionary with server info
        """
        return self._json_rpc('/jsonrpc', 'call', {
            'service': 'common',
            'method': 'version',
            'args': []
        })
    
    @keyword("Get Databases")
    def get_databases(self):
        """
        Get list of available databases
        
        Returns:
            List of database names
        """
        return self._json_rpc('/jsonrpc', 'call', {
            'service': 'db',
            'method': 'list',
            'args': []
        })
