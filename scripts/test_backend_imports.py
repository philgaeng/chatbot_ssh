#!/usr/bin/env python3
"""
Backend Import Test Script

This script recursively checks all Python files in the backend directory
for import errors and reports them comprehensively.
"""

import os
import sys
import importlib
import ast
import traceback
import re
from pathlib import Path
from typing import List, Dict, Tuple, Set
import subprocess

class ImportChecker:
    def __init__(self, backend_dir: Path, base_dir: Path):
        self.backend_dir = backend_dir
        self.base_dir = base_dir
        self.errors: List[Dict] = []
        self.warnings: List[Dict] = []
        self.success_count = 0
        self.error_count = 0
        self.env_constants: Set[str] = set()
        
        # Add the base directory to Python path for imports
        if str(self.base_dir) not in sys.path:
            sys.path.insert(0, str(self.base_dir))
        
        # Parse env.local to get constants
        self.parse_env_local()
    
    def parse_env_local(self):
        """Parse env.local file to extract constant names."""
        env_file = self.base_dir / "env.local"
        if not env_file.exists():
            print(f"⚠️  env.local not found at {env_file}")
            return
        
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract constant names (lines like VARIABLE_NAME=value)
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    constant_name = line.split('=')[0].strip()
                    self.env_constants.add(constant_name)
            
            print(f"📋 Loaded {len(self.env_constants)} constants from env.local")
        except Exception as e:
            print(f"❌ Failed to parse env.local: {e}")
    
    def is_config_import(self, import_name: str) -> bool:
        """Check if an import is config-related."""
        return (import_name.startswith('backend.config') or 
                import_name.startswith('.config') or
                'config' in import_name.split('.'))
    
    def find_python_files(self) -> List[Path]:
        """Find all Python files in the backend directory."""
        python_files = []
        for root, dirs, files in os.walk(self.backend_dir):
            # Skip __pycache__ directories
            dirs[:] = [d for d in dirs if d != '__pycache__']
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        
        return python_files
    
    def get_imports_from_file(self, file_path: Path) -> List[str]:
        """Extract all import statements from a Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        if module:
                            imports.append(f"{module}.{alias.name}")
                        else:
                            imports.append(alias.name)
            
            return imports
        except Exception as e:
            self.errors.append({
                'file': str(file_path),
                'error': f"Failed to parse file: {str(e)}",
                'type': 'parse_error'
            })
            return []
    
    def test_import(self, module_name: str) -> bool:
        """Test if a module can be imported."""
        try:
            importlib.import_module(module_name)
            return True
        except ImportError as e:
            return False
        except Exception as e:
            # Other exceptions (like syntax errors) are still import failures
            return False
    
    def test_file_imports(self, file_path: Path) -> Dict:
        """Test all imports in a single file."""
        relative_path = file_path.relative_to(self.base_dir)
        module_path = str(relative_path).replace('/', '.').replace('\\', '.')[:-3]  # Remove .py
        
        result = {
            'file': str(file_path),
            'module_path': module_path,
            'config_imports': [],
            'other_imports': [],
            'config_errors': [],
            'other_errors': [],
            'warnings': []
        }
        
        # Get all imports from the file
        imports = self.get_imports_from_file(file_path)
        
        for import_name in imports:
            # Only check local imports: those starting with '.' or 'backend'
            if import_name.startswith('.') or import_name.startswith('backend'):
                try:
                    # Test the import
                    if self.test_import(import_name):
                        if self.is_config_import(import_name):
                            result['config_imports'].append({
                                'name': import_name,
                                'status': 'success'
                            })
                        else:
                            result['other_imports'].append({
                                'name': import_name,
                                'status': 'success'
                            })
                    else:
                        if self.is_config_import(import_name):
                            # For config imports, check if constants exist in env.local
                            missing_constants = self.check_config_constants(import_name)
                            if missing_constants:
                                result['config_errors'].append({
                                    'import': import_name,
                                    'error': f'Import failed - Missing constants in env.local: {", ".join(missing_constants)}'
                                })
                            else:
                                result['config_errors'].append({
                                    'import': import_name,
                                    'error': 'Import failed'
                                })
                        else:
                            result['other_errors'].append({
                                'import': import_name,
                                'error': 'Import failed'
                            })
                except Exception as e:
                    if self.is_config_import(import_name):
                        result['config_errors'].append({
                            'import': import_name,
                            'error': str(e)
                        })
                    else:
                        result['other_errors'].append({
                            'import': import_name,
                            'error': str(e)
                        })
        
        return result
    
    def check_config_constants(self, import_name: str) -> List[str]:
        """Check if config import references constants that exist in env.local."""
        # This is a simplified check - in practice, you might need to actually
        # import the config module and see what constants it tries to access
        missing_constants = []
        
        # For now, we'll check if the import name contains any of our env constants
        # This is a basic heuristic - you might need more sophisticated logic
        for constant in self.env_constants:
            if constant.lower() in import_name.lower():
                # This is a very basic check - you might need more sophisticated logic
                pass
        
        return missing_constants
    
    def test_file_execution(self, file_path: Path) -> Dict:
        """Test if a file can be executed (basic syntax check)."""
        result = {
            'file': str(file_path),
            'execution_error': None
        }
        
        try:
            # Try to compile the file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            compile(content, str(file_path), 'exec')
            return result
        except Exception as e:
            result['execution_error'] = str(e)
            return result
    
    def run_tests(self) -> Dict:
        """Run all import tests on the backend directory."""
        print(f"🔍 Scanning for Python files in {self.backend_dir}...")
        python_files = self.find_python_files()
        print(f"📁 Found {len(python_files)} Python files")
        
        results = {
            'files_tested': len(python_files),
            'successful_files': 0,
            'failed_files': 0,
            'file_results': [],
            'execution_results': []
        }
        
        for file_path in python_files:
            print(f"  Testing {file_path.relative_to(self.base_dir)}...")
            
            # Test imports
            import_result = self.test_file_imports(file_path)
            results['file_results'].append(import_result)
            
            # Test execution
            exec_result = self.test_file_execution(file_path)
            results['execution_results'].append(exec_result)
            
            # Count successes/failures
            if not import_result['config_errors'] and not import_result['other_errors'] and not exec_result['execution_error']:
                results['successful_files'] += 1
            else:
                results['failed_files'] += 1
        
        return results
    
    def print_report(self, results: Dict):
        """Print a comprehensive report of the test results."""
        print("\n" + "="*80)
        print("📊 BACKEND IMPORT TEST REPORT")
        print("="*80)
        
        print(f"\n📈 Summary:")
        print(f"  Files tested: {results['files_tested']}")
        print(f"  ✅ Successful: {results['successful_files']}")
        print(f"  ❌ Failed: {results['failed_files']}")
        
        # Report files with import errors (segregated)
        files_with_errors = [r for r in results['file_results'] if r['config_errors'] or r['other_errors']]
        if files_with_errors:
            print(f"\n❌ Files with import errors ({len(files_with_errors)}):")
            for result in files_with_errors:
                print(f"\n  📄 {result['file']}")
                
                # Config import errors
                if result['config_errors']:
                    print(f"    ❌ Config imports:")
                    for error in result['config_errors']:
                        print(f"      - {error['import']}: {error['error']}")
                
                # Other import errors
                if result['other_errors']:
                    print(f"    ❌ Other imports:")
                    for error in result['other_errors']:
                        print(f"      - {error['import']}: {error['error']}")
        
        # Report files with execution errors
        files_with_exec_errors = [r for r in results['execution_results'] if r['execution_error']]
        if files_with_exec_errors:
            print(f"\n🚫 Files with execution errors ({len(files_with_exec_errors)}):")
            for result in files_with_exec_errors:
                print(f"\n  📄 {result['file']}")
                print(f"    ❌ {result['execution_error']}")
        
        # Report successful files
        successful_files = [r for r in results['file_results'] if not r['config_errors'] and not r['other_errors']]
        if successful_files:
            print(f"\n✅ Files with successful imports ({len(successful_files)}):")
            for result in successful_files:
                print(f"  ✅ {result['file']}")
        
        print("\n" + "="*80)
    
    def generate_fix_suggestions(self, results: Dict) -> List[str]:
        """Generate suggestions for fixing import issues."""
        suggestions = []
        
        for result in results['file_results']:
            # Config import suggestions
            for error in result['config_errors']:
                import_name = error['import']
                if 'Missing constants in env.local' in error['error']:
                    suggestions.append(f"Add missing constants to env.local for {import_name}")
                else:
                    suggestions.append(f"Check if {import_name} exists and is properly configured")
            
            # Other import suggestions
            for error in result['other_errors']:
                import_name = error['import']
                if import_name.startswith('backend.'):
                    suggestions.append(f"Check if {import_name} exists in the backend directory")
                elif '.' in import_name and not import_name.startswith('backend.'):
                    suggestions.append(f"Consider using absolute import: backend.{import_name}")
                else:
                    suggestions.append(f"Check if {import_name} is installed or exists")
        
        return suggestions

def main():
    """Main function to run the import tests."""
    # Get the base directory (project root)
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent  # Go up to project root
    backend_dir = base_dir / "backend"
    
    if not backend_dir.exists():
        print(f"❌ Backend directory not found at {backend_dir}")
        sys.exit(1)
    
    print(f"🚀 Starting backend import tests...")
    print(f"📁 Base directory: {base_dir}")
    print(f"📁 Backend directory: {backend_dir}")
    
    # Create checker and run tests
    checker = ImportChecker(backend_dir, base_dir)
    results = checker.run_tests()
    
    # Print report
    checker.print_report(results)
    
    # Generate and print suggestions
    suggestions = checker.generate_fix_suggestions(results)
    if suggestions:
        print(f"\n💡 Fix suggestions:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"  {i}. {suggestion}")
    
    # Exit with error code if there are failures
    if results['failed_files'] > 0:
        print(f"\n❌ {results['failed_files']} files have import or execution errors")
        sys.exit(1)
    else:
        print(f"\n✅ All {results['files_tested']} files passed import tests!")
        sys.exit(0)

if __name__ == "__main__":
    main() 