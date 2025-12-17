"""
DOCUMENTATION EXTRACTOR
TreeSitter-style tool to extract all system structure

SUPERVISOR'S REQUIREMENT:
"List all folders, files, classes, functions with arguments and returns.
 If you create code for that, any alteration just run again and everything updated."
"""

import ast
import os
import json
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict


@dataclass
class FunctionSignature:
    """Function signature information"""
    name: str
    arguments: List[Dict[str, str]]  # [{name, type, default}]
    return_type: str
    docstring: str
    line_number: int
    classification: str  # "Brain Capacity" / "Knowledge" / "Intelligence"


@dataclass
class ClassInfo:
    """Class information"""
    name: str
    docstring: str
    methods: List[FunctionSignature]
    line_number: int
    classification: str


@dataclass
class FileInfo:
    """File information"""
    filepath: str
    classes: List[ClassInfo]
    functions: List[FunctionSignature]
    imports: List[str]


class DocumentationExtractor:
    """
    Extracts complete system structure
    
    Supervisor: "Then we know what's working, what's not.
                We know where to put new features."
    """
    
    def __init__(self, root_path: str):
        """
        Initialize documentation extractor
        
        Args:
            root_path: Root directory to scan
        """
        self.root_path = Path(root_path)
        self.files_info: List[FileInfo] = []
        
        # Classification keywords
        self.capacity_keywords = [
            'capacity', 'manager', 'storage', 'sensor', 'action', 'feedback'
        ]
        self.knowledge_keywords = [
            'knowledge', 'graph', 'memory', 'state', 'record'
        ]
        self.intelligence_keywords = [
            'intelligence', 'awareness', 'decision', 'plan', 'constraint'
        ]
    
    def extract_all(self) -> Dict[str, Any]:
        """
        Extract complete system structure
        
        Returns:
            Complete documentation dictionary
        """
        print("="*80)
        print("EXTRACTING SYSTEM DOCUMENTATION")
        print("="*80)
        
        # Scan all Python files
        python_files = list(self.root_path.rglob("*.py"))
        
        print(f"\nFound {len(python_files)} Python files")
        
        for filepath in python_files:
            try:
                file_info = self._extract_file(filepath)
                self.files_info.append(file_info)
            except Exception as e:
                print(f"  ✗ Error processing {filepath.name}: {e}")
        
        # Generate documentation
        doc = self._generate_documentation()
        
        print(f"\n✓ Documentation extracted for {len(self.files_info)} files")
        
        return doc
    
    def _extract_file(self, filepath: Path) -> FileInfo:
        """Extract information from single file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source)
        
        classes = []
        functions = []
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = self._extract_class(node, str(filepath))
                classes.append(class_info)
            elif isinstance(node, ast.FunctionDef):
                # Top-level functions only
                if node.col_offset == 0:
                    func_info = self._extract_function(node, str(filepath))
                    functions.append(func_info)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.extend(self._extract_imports(node))
        
        return FileInfo(
            filepath=str(filepath.relative_to(self.root_path)),
            classes=classes,
            functions=functions,
            imports=imports
        )
    
    def _extract_class(self, node: ast.ClassDef, filepath: str) -> ClassInfo:
        """Extract class information"""
        methods = []
        
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_info = self._extract_function(item, filepath)
                methods.append(method_info)
        
        # Classify class
        classification = self._classify_component(node.name, ast.get_docstring(node) or "")
        
        return ClassInfo(
            name=node.name,
            docstring=ast.get_docstring(node) or "",
            methods=methods,
            line_number=node.lineno,
            classification=classification
        )
    
    def _extract_function(self, node: ast.FunctionDef, filepath: str) -> FunctionSignature:
        """Extract function signature"""
        # Extract arguments
        arguments = []
        for arg in node.args.args:
            arg_info = {
                'name': arg.arg,
                'type': self._get_type_annotation(arg),
                'default': None
            }
            arguments.append(arg_info)
        
        # Extract defaults
        defaults = node.args.defaults
        if defaults:
            for i, default in enumerate(defaults):
                idx = len(arguments) - len(defaults) + i
                if idx >= 0:
                    arguments[idx]['default'] = ast.unparse(default)
        
        # Extract return type
        return_type = "Any"
        if node.returns:
            return_type = ast.unparse(node.returns)
        
        # Classify function
        classification = self._classify_component(
            node.name,
            ast.get_docstring(node) or ""
        )
        
        return FunctionSignature(
            name=node.name,
            arguments=arguments,
            return_type=return_type,
            docstring=ast.get_docstring(node) or "",
            line_number=node.lineno,
            classification=classification
        )
    
    def _get_type_annotation(self, arg: ast.arg) -> str:
        """Get type annotation for argument"""
        if arg.annotation:
            return ast.unparse(arg.annotation)
        return "Any"
    
    def _extract_imports(self, node) -> List[str]:
        """Extract import statements"""
        imports = []
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")
        return imports
    
    def _classify_component(self, name: str, docstring: str) -> str:
        """
        Classify component as Brain Capacity / Knowledge / Intelligence
        
        Supervisor's Framework:
        - Brain Capacity: What system CAN do
        - Knowledge: What system KNOWS
        - Intelligence: How system USES capacity + knowledge
        """
        text = (name + " " + docstring).lower()
        
        # Check for intelligence indicators
        if any(keyword in text for keyword in self.intelligence_keywords):
            return "Intelligence"
        
        # Check for knowledge indicators
        if any(keyword in text for keyword in self.knowledge_keywords):
            return "Knowledge"
        
        # Check for capacity indicators
        if any(keyword in text for keyword in self.capacity_keywords):
            return "Brain Capacity"
        
        return "Unclassified"
    
    def _generate_documentation(self) -> Dict[str, Any]:
        """Generate complete documentation structure"""
        doc = {
            'system_overview': {
                'total_files': len(self.files_info),
                'total_classes': sum(len(f.classes) for f in self.files_info),
                'total_functions': sum(
                    len(f.functions) + sum(len(c.methods) for c in f.classes)
                    for f in self.files_info
                )
            },
            'files': []
        }
        
        for file_info in self.files_info:
            file_doc = {
                'filepath': file_info.filepath,
                'imports': file_info.imports,
                'classes': [],
                'functions': []
            }
            
            # Document classes
            for class_info in file_info.classes:
                class_doc = {
                    'name': class_info.name,
                    'classification': class_info.classification,
                    'docstring': class_info.docstring[:200],  # First 200 chars
                    'line': class_info.line_number,
                    'methods': []
                }
                
                for method in class_info.methods:
                    method_doc = self._document_function(method)
                    class_doc['methods'].append(method_doc)
                
                file_doc['classes'].append(class_doc)
            
            # Document functions
            for func_info in file_info.functions:
                func_doc = self._document_function(func_info)
                file_doc['functions'].append(func_doc)
            
            doc['files'].append(file_doc)
        
        return doc
    
    def _document_function(self, func: FunctionSignature) -> Dict[str, Any]:
        """Document single function"""
        # Build signature string
        args_str = ", ".join([
            f"{arg['name']}: {arg['type']}" + 
            (f" = {arg['default']}" if arg['default'] else "")
            for arg in func.arguments
        ])
        
        signature = f"{func.name}({args_str}) -> {func.return_type}"
        
        return {
            'signature': signature,
            'classification': func.classification,
            'docstring': func.docstring[:200],  # First 200 chars
            'line': func.line_number
        }
    
    def export_markdown(self, output_path: str):
        """Export documentation as Markdown"""
        doc = self.extract_all()
        
        md_lines = []
        md_lines.append("# System Documentation\n")
        md_lines.append("## Overview\n")
        md_lines.append(f"- Total Files: {doc['system_overview']['total_files']}")
        md_lines.append(f"- Total Classes: {doc['system_overview']['total_classes']}")
        md_lines.append(f"- Total Functions: {doc['system_overview']['total_functions']}\n")
        
        md_lines.append("## Files\n")
        
        for file_doc in doc['files']:
            md_lines.append(f"### {file_doc['filepath']}\n")
            
            if file_doc['classes']:
                md_lines.append("#### Classes\n")
                for class_doc in file_doc['classes']:
                    md_lines.append(f"**{class_doc['name']}** - *{class_doc['classification']}*")
                    md_lines.append(f"> {class_doc['docstring']}\n")
                    
                    if class_doc['methods']:
                        md_lines.append("Methods:")
                        for method in class_doc['methods']:
                            md_lines.append(f"- `{method['signature']}` - *{method['classification']}*")
                        md_lines.append("")
            
            if file_doc['functions']:
                md_lines.append("#### Functions\n")
                for func_doc in file_doc['functions']:
                    md_lines.append(f"- `{func_doc['signature']}` - *{func_doc['classification']}*")
                md_lines.append("")
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(md_lines))
        
        print(f"\n✓ Documentation exported to {output_path}")
    
    def export_json(self, output_path: str):
        """Export documentation as JSON"""
        doc = self.extract_all()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(doc, f, indent=2)
        
        print(f"✓ Documentation exported to {output_path}")


# ============================================================================
# USAGE
# ============================================================================

if __name__ == "__main__":
    extractor = DocumentationExtractor("/app")
    
    # Export as Markdown (human-readable)
    extractor.export_markdown("/app/SYSTEM_DOCUMENTATION.md")
    
    # Export as JSON (machine-readable)
    extractor.export_json("/app/system_documentation.json")
    
    print("\n" + "="*80)
    print("✓ DOCUMENTATION EXTRACTION COMPLETE")
    print("="*80)