import json
import re
import logging
from datetime import datetime, timedelta

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MigrationDataTransformer(models.AbstractModel):
    _name = 'migration.data.transformer'
    _description = 'Data Transformation Service'

    @api.model
    def apply_transformation(self, value, transformation_type, params_json):
        """
        Apply a transformation to a value.
        
        Args:
            value: The input value to transform
            transformation_type: Type of transformation to apply
            params_json: JSON string with transformation parameters
        
        Returns:
            Transformed value
        """
        if value is None:
            return None
        
        params = json.loads(params_json) if params_json else {}
        
        # Get transformation method
        method_name = f'_transform_{transformation_type}'
        if hasattr(self, method_name):
            try:
                return getattr(self, method_name)(value, params)
            except Exception as e:
                _logger.warning(f"Transformation error ({transformation_type}): {e}")
                return value
        else:
            _logger.warning(f"Unknown transformation type: {transformation_type}")
            return value
    
    # ==================
    # String Transformations
    # ==================
    
    def _transform_uppercase(self, value, params):
        """Convert to uppercase."""
        return str(value).upper()
    
    def _transform_lowercase(self, value, params):
        """Convert to lowercase."""
        return str(value).lower()
    
    def _transform_titlecase(self, value, params):
        """Convert to title case."""
        return str(value).title()
    
    def _transform_trim(self, value, params):
        """Trim whitespace."""
        return str(value).strip()
    
    def _transform_replace(self, value, params):
        """Find and replace text."""
        find = params.get('find', '')
        replace = params.get('replace', '')
        return str(value).replace(find, replace)
    
    def _transform_regex_replace(self, value, params):
        """Regex find and replace."""
        pattern = params.get('pattern', '')
        replace = params.get('replace', '')
        return re.sub(pattern, replace, str(value))
    
    def _transform_prefix(self, value, params):
        """Add prefix."""
        prefix = params.get('prefix', '')
        return f"{prefix}{value}"
    
    def _transform_suffix(self, value, params):
        """Add suffix."""
        suffix = params.get('suffix', '')
        return f"{value}{suffix}"
    
    def _transform_truncate(self, value, params):
        """Truncate to length."""
        length = params.get('length', 100)
        suffix = params.get('suffix', '...')
        text = str(value)
        if len(text) > length:
            return text[:length - len(suffix)] + suffix
        return text
    
    def _transform_extract(self, value, params):
        """Extract using regex pattern."""
        pattern = params.get('pattern', '(.*)')
        match = re.search(pattern, str(value))
        if match:
            return match.group(1) if match.groups() else match.group(0)
        return ''
    
    def _transform_split(self, value, params):
        """Split string and return specific index."""
        delimiter = params.get('delimiter', ',')
        index = params.get('index', 0)
        parts = str(value).split(delimiter)
        if 0 <= index < len(parts):
            return parts[index].strip()
        return ''
    
    def _transform_join(self, value, params):
        """Join list values."""
        delimiter = params.get('delimiter', ', ')
        if isinstance(value, list):
            return delimiter.join(str(v) for v in value)
        return str(value)
    
    # ==================
    # Numeric Transformations
    # ==================
    
    def _transform_round(self, value, params):
        """Round to decimal places."""
        decimals = params.get('decimals', 2)
        try:
            return round(float(value), decimals)
        except (ValueError, TypeError):
            return value
    
    def _transform_multiply(self, value, params):
        """Multiply by factor."""
        factor = params.get('factor', 1)
        try:
            return float(value) * factor
        except (ValueError, TypeError):
            return value
    
    def _transform_divide(self, value, params):
        """Divide by divisor."""
        divisor = params.get('divisor', 1)
        if divisor == 0:
            return value
        try:
            return float(value) / divisor
        except (ValueError, TypeError):
            return value
    
    def _transform_add(self, value, params):
        """Add value."""
        add_value = params.get('value', 0)
        try:
            return float(value) + add_value
        except (ValueError, TypeError):
            return value
    
    def _transform_subtract(self, value, params):
        """Subtract value."""
        sub_value = params.get('value', 0)
        try:
            return float(value) - sub_value
        except (ValueError, TypeError):
            return value
    
    def _transform_abs(self, value, params):
        """Absolute value."""
        try:
            return abs(float(value))
        except (ValueError, TypeError):
            return value
    
    def _transform_clean_numeric(self, value, params):
        """Clean numeric value by removing non-numeric characters."""
        # Keep only digits, decimal point, and minus sign
        cleaned = re.sub(r'[^\d.\-]', '', str(value))
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    
    # ==================
    # Date Transformations
    # ==================
    
    def _transform_date_format(self, value, params):
        """Reformat date string."""
        input_format = params.get('input_format', '%Y-%m-%d')
        output_format = params.get('output_format', '%Y-%m-%d')
        
        # Try multiple input formats if not specified
        if not params.get('input_format'):
            formats = [
                '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y',
                '%Y/%m/%d', '%d.%m.%Y', '%Y-%m-%d %H:%M:%S',
                '%d/%m/%Y %H:%M:%S', '%m/%d/%Y %H:%M:%S',
            ]
        else:
            formats = [input_format]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(str(value), fmt)
                return dt.strftime(output_format)
            except ValueError:
                continue
        
        return value
    
    def _transform_date_add_days(self, value, params):
        """Add days to date."""
        days = params.get('days', 0)
        input_format = params.get('format', '%Y-%m-%d')
        
        try:
            dt = datetime.strptime(str(value), input_format)
            new_dt = dt + timedelta(days=days)
            return new_dt.strftime(input_format)
        except ValueError:
            return value
    
    def _transform_date_to_year(self, value, params):
        """Extract year from date."""
        input_format = params.get('format', '%Y-%m-%d')
        try:
            dt = datetime.strptime(str(value), input_format)
            return dt.year
        except ValueError:
            return value
    
    def _transform_date_to_month(self, value, params):
        """Extract month from date."""
        input_format = params.get('format', '%Y-%m-%d')
        try:
            dt = datetime.strptime(str(value), input_format)
            return dt.month
        except ValueError:
            return value
    
    # ==================
    # Mapping Transformations
    # ==================
    
    def _transform_value_map(self, value, params):
        """Map value using lookup table."""
        mapping = params.get('mapping', {})
        default = params.get('default')
        case_insensitive = params.get('case_insensitive', False)
        
        str_value = str(value)
        
        if case_insensitive:
            str_value_lower = str_value.lower()
            for key, mapped_value in mapping.items():
                if str(key).lower() == str_value_lower:
                    return mapped_value
        else:
            if str_value in mapping:
                return mapping[str_value]
        
        return default if default is not None else value
    
    def _transform_lookup(self, value, params):
        """Lookup value in Odoo model."""
        model = params.get('model')
        search_field = params.get('search_field', 'name')
        return_field = params.get('return_field', 'id')
        
        if not model:
            return value
        
        try:
            record = self.env[model].search([(search_field, '=', value)], limit=1)
            if record:
                return getattr(record, return_field)
        except Exception as e:
            _logger.warning(f"Lookup error: {e}")
        
        return value
    
    # ==================
    # Special Transformations
    # ==================
    
    def _transform_coalesce(self, value, params):
        """Return first non-empty value."""
        alternatives = params.get('alternatives', [])
        
        if value and str(value).strip():
            return value
        
        for alt in alternatives:
            if alt and str(alt).strip():
                return alt
        
        return params.get('default', '')
    
    def _transform_conditional(self, value, params):
        """Conditional transformation."""
        condition = params.get('condition', '')
        true_value = params.get('true_value', value)
        false_value = params.get('false_value', value)
        
        try:
            # Simple condition evaluation
            # Supports: ==, !=, >, <, >=, <=, contains, startswith, endswith
            if '==' in condition:
                parts = condition.split('==')
                result = str(value) == parts[1].strip().strip('"\'')
            elif '!=' in condition:
                parts = condition.split('!=')
                result = str(value) != parts[1].strip().strip('"\'')
            elif 'contains' in condition:
                parts = condition.split('contains')
                result = parts[1].strip().strip('"\'') in str(value)
            elif 'startswith' in condition:
                parts = condition.split('startswith')
                result = str(value).startswith(parts[1].strip().strip('"\''))
            elif 'endswith' in condition:
                parts = condition.split('endswith')
                result = str(value).endswith(parts[1].strip().strip('"\''))
            elif '>' in condition and '=' not in condition:
                parts = condition.split('>')
                result = float(value) > float(parts[1].strip())
            elif '<' in condition and '=' not in condition:
                parts = condition.split('<')
                result = float(value) < float(parts[1].strip())
            elif '>=' in condition:
                parts = condition.split('>=')
                result = float(value) >= float(parts[1].strip())
            elif '<=' in condition:
                parts = condition.split('<=')
                result = float(value) <= float(parts[1].strip())
            else:
                result = bool(value)
            
            return true_value if result else false_value
            
        except Exception as e:
            _logger.warning(f"Conditional evaluation error: {e}")
            return false_value
    
    def _transform_python(self, value, params):
        """
        Execute Python expression.
        WARNING: Only use in trusted environments!
        """
        expression = params.get('expression', 'value')
        
        # Security: Only allow safe operations
        allowed_names = {
            'value': value,
            'str': str,
            'int': int,
            'float': float,
            'len': len,
            'bool': bool,
            'min': min,
            'max': max,
            'abs': abs,
            'round': round,
            'upper': lambda v: str(v).upper(),
            'lower': lambda v: str(v).lower(),
            'strip': lambda v: str(v).strip(),
            'replace': lambda v, old, new: str(v).replace(old, new),
            'split': lambda v, sep=',': str(v).split(sep),
            'join': lambda lst, sep=',': sep.join(str(i) for i in lst),
        }
        
        # Check for dangerous patterns
        dangerous_patterns = [
            '__', 'import', 'exec', 'eval', 'open', 'file',
            'compile', 'globals', 'locals', 'getattr', 'setattr',
        ]
        
        for pattern in dangerous_patterns:
            if pattern in expression.lower():
                _logger.warning(f"Blocked dangerous expression: {expression}")
                return value
        
        try:
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            return result
        except Exception as e:
            _logger.warning(f"Python expression error: {e}")
            return value
    
    # ==================
    # Batch Processing
    # ==================
    
    @api.model
    def apply_transformations_batch(self, values, transformations):
        """
        Apply a series of transformations to multiple values.
        
        Args:
            values: List of input values
            transformations: List of (type, params) tuples
        
        Returns:
            List of transformed values
        """
        results = []
        for value in values:
            result = value
            for trans_type, params in transformations:
                result = self.apply_transformation(result, trans_type, params)
            results.append(result)
        return results
    
    @api.model
    def preview_transformation(self, value, transformation_type, params_json):
        """
        Preview a transformation without saving.
        
        Returns dict with original, transformed, and any errors.
        """
        try:
            transformed = self.apply_transformation(value, transformation_type, params_json)
            return {
                'success': True,
                'original': value,
                'transformed': transformed,
                'error': None,
            }
        except Exception as e:
            return {
                'success': False,
                'original': value,
                'transformed': None,
                'error': str(e),
            }
