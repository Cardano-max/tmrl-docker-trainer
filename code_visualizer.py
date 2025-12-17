"""
ENHANCED INTERACTIVE CODE VISUALIZER - HORIZONTAL EDITION
Highly readable left-to-right tree layout for large codebases
Perfect for presentations with 49+ modules
"""

import ast
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class Parameter:
    name: str
    type_hint: str
    default: Optional[str] = None


@dataclass
class Function:
    name: str
    line_number: int
    return_type: str
    parameters: List[Parameter]
    docstring: str
    is_method: bool = False
    classification: str = "Unclassified"


@dataclass
class Variable:
    name: str
    type_hint: str
    line_number: int
    value: Optional[str] = None


@dataclass
class Class:
    name: str
    line_number: int
    docstring: str
    methods: List[Function]
    variables: List[Variable]
    classification: str = "Unclassified"


@dataclass
class Module:
    name: str
    path: str
    classes: List[Class]
    functions: List[Function]
    variables: List[Variable]
    imports: List[str]
    classification: str = "Unclassified"


class CodeVisualizer:
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.modules: List[Module] = []
        
        self.capacity_keywords = [
            'timestamp', 'state', 'memory', 'brain', 'manager', 
            'handler', 'core', 'capacity'
        ]
        self.knowledge_keywords = [
            'knowledge', 'graph', 'record', 'store', 'data'
        ]
        self.intelligence_keywords = [
            'intelligence', 'awareness', 'decision', 'plan', 
            'constraint', 'monitor', 'explore', 'repeat'
        ]
    
    def analyze_system(self) -> Dict[str, Any]:
        print("="*80)
        print("ANALYZING SYSTEM FOR VISUALIZATION")
        print("="*80)
        
        python_files = list(self.root_path.rglob("*.py"))
        print(f"\nFound {len(python_files)} Python files")
        
        for filepath in python_files:
            try:
                module = self._analyze_file(filepath)
                self.modules.append(module)
                print(f"  ✓ {filepath.name}")
            except Exception as e:
                print(f"  ✗ {filepath.name}: {e}")
        
        print(f"\n✓ Analyzed {len(self.modules)} modules")
        
        return self._generate_structure()
    
    def _analyze_file(self, filepath: Path) -> Module:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source)
        
        classes = []
        functions = []
        variables = []
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = self._extract_class(node)
                classes.append(class_info)
            elif isinstance(node, ast.FunctionDef):
                if node.col_offset == 0:
                    func_info = self._extract_function(node, is_method=False)
                    functions.append(func_info)
            elif isinstance(node, ast.Assign):
                if node.col_offset == 0:
                    var_info = self._extract_variable(node)
                    if var_info:
                        variables.append(var_info)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.extend(self._extract_imports(node))
        
        classification = self._classify_component(
            filepath.stem, 
            " ".join([c.name for c in classes] + [f.name for f in functions])
        )
        
        return Module(
            name=filepath.stem,
            path=str(filepath.relative_to(self.root_path)),
            classes=classes,
            functions=functions,
            variables=variables,
            imports=imports,
            classification=classification
        )
    
    def _extract_class(self, node: ast.ClassDef) -> Class:
        methods = []
        variables = []
        
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method = self._extract_function(item, is_method=True)
                methods.append(method)
            elif isinstance(item, ast.Assign):
                var = self._extract_variable(item)
                if var:
                    variables.append(var)
        
        classification = self._classify_component(
            node.name, 
            ast.get_docstring(node) or ""
        )
        
        return Class(
            name=node.name,
            line_number=node.lineno,
            docstring=ast.get_docstring(node) or "",
            methods=methods,
            variables=variables,
            classification=classification
        )
    
    def _extract_function(self, node: ast.FunctionDef, is_method: bool) -> Function:
        parameters = []
        for arg in node.args.args:
            if is_method and arg.arg in ('self', 'cls'):
                continue
                
            param = Parameter(
                name=arg.arg,
                type_hint=self._get_type_annotation(arg),
                default=None
            )
            parameters.append(param)
        
        defaults = node.args.defaults
        if defaults:
            for i, default in enumerate(defaults):
                idx = len(parameters) - len(defaults) + i
                if idx >= 0 and idx < len(parameters):
                    parameters[idx].default = ast.unparse(default)
        
        return_type = "Any"
        if node.returns:
            return_type = ast.unparse(node.returns)
        
        classification = self._classify_component(
            node.name,
            ast.get_docstring(node) or ""
        )
        
        return Function(
            name=node.name,
            line_number=node.lineno,
            return_type=return_type,
            parameters=parameters,
            docstring=ast.get_docstring(node) or "",
            is_method=is_method,
            classification=classification
        )
    
    def _extract_variable(self, node: ast.Assign) -> Optional[Variable]:
        if not node.targets:
            return None
        
        target = node.targets[0]
        if isinstance(target, ast.Name):
            type_hint = "Any"
            value = None
            
            if isinstance(node.value, ast.Constant):
                type_hint = type(node.value.value).__name__
                value = str(node.value.value)
            elif isinstance(node.value, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
                type_hint = type(node.value).__name__
            
            return Variable(
                name=target.id,
                type_hint=type_hint,
                line_number=node.lineno,
                value=value
            )
        
        return None
    
    def _get_type_annotation(self, arg: ast.arg) -> str:
        if arg.annotation:
            return ast.unparse(arg.annotation)
        return "Any"
    
    def _extract_imports(self, node) -> List[str]:
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
        text = (name + " " + docstring).lower()
        
        if any(kw in text for kw in self.intelligence_keywords):
            return "Intelligence"
        elif any(kw in text for kw in self.knowledge_keywords):
            return "Knowledge"
        elif any(kw in text for kw in self.capacity_keywords):
            return "Brain Capacity"
        
        return "Unclassified"
    
    def _generate_structure(self) -> Dict[str, Any]:
        return {
            'metadata': {
                'total_modules': len(self.modules),
                'total_classes': sum(len(m.classes) for m in self.modules),
                'total_functions': sum(
                    len(m.functions) + sum(len(c.methods) for c in m.classes)
                    for m in self.modules
                ),
                'analysis_complete': True
            },
            'modules': [asdict(m) for m in self.modules]
        }
    
    def _generate_hierarchy_for_d3(self) -> Dict[str, Any]:
        root = {
            "name": "System Root",
            "classification": "All",
            "children": []
        }

        for module in self.modules:
            mod_node = {
                "name": f"{module.name}.py",
                "path": module.path,
                "classification": module.classification,
                "badge": module.classification if module.classification != "Unclassified" else None,
                "children": []
            }

            for func in module.functions:
                params_str = ", ".join(
                    f"{p.name}: {p.type_hint}" + (f" = {p.default}" if p.default else "")
                    for p in func.parameters
                )
                mod_node["children"].append({
                    "name": f"def {func.name}({params_str}) → {func.return_type}",
                    "details": func.docstring.strip() if func.docstring else "No docstring",
                    "classification": func.classification
                })

            for var in module.variables:
                value_str = f" = {var.value}" if var.value else ""
                mod_node["children"].append({
                    "name": f"{var.name}: {var.type_hint}{value_str}",
                    "details": "Global variable",
                    "classification": module.classification
                })

            for cls in module.classes:
                class_node = {
                    "name": f"class {cls.name}",
                    "badge": cls.classification if cls.classification != "Unclassified" else None,
                    "details": cls.docstring.strip() if cls.docstring else "No docstring",
                    "children": []
                }

                for var in cls.variables:
                    value_str = f" = {var.value}" if var.value else ""
                    class_node["children"].append({
                        "name": f"{var.name}: {var.type_hint}{value_str}",
                        "details": "Class variable"
                    })

                for method in cls.methods:
                    params_str = ", ".join(
                        f"{p.name}: {p.type_hint}" + (f" = {p.default}" if p.default else "")
                        for p in method.parameters
                    )
                    class_node["children"].append({
                        "name": f"def {method.name}({params_str}) → {method.return_type}",
                        "details": method.docstring.strip() if method.docstring else "No docstring",
                        "classification": method.classification
                    })

                mod_node["children"].append(class_node)

            root["children"].append(mod_node)

        return root
    
    def generate_interactive_html(self, output_path: str):
        structure = self.analyze_system()
        html = self._create_html_template(structure)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"\n✓ Interactive visualization created: {output_path}")
    
    def _create_html_template(self, structure: Dict[str, Any]) -> str:
        hierarchy = self._generate_hierarchy_for_d3()
        hierarchy_json = json.dumps(hierarchy)

        stats_html = (
            f"Modules: {structure['metadata']['total_modules']} | "
            f"Classes: {structure['metadata']['total_classes']} | "
            f"Functions/Methods: {structure['metadata']['total_functions']}"
        )

        html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Code Visualizer - Horizontal Tree</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body { margin:0; font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #1e3c72, #2a5298); color: white; overflow: hidden; }
        .header { padding: 20px; text-align: center; background: rgba(0,0,0,0.3); backdrop-filter: blur(10px); }
        .header h1 { font-size: 2.5em; margin: 0; }
        .stats { margin: 10px 0; font-size: 1.2em; font-weight: bold; }
        .controls { margin: 15px 0; }
        .search { padding: 12px 20px; width: 450px; border-radius: 30px; border: none; font-size: 1.1em; }
        .filters { margin-top: 15px; }
        .filter-btn { padding: 12px 24px; margin: 8px; border: none; border-radius: 30px; cursor: pointer; font-weight: bold; font-size: 1em; }
        .filter-btn.active { background: #4facfe; transform: scale(1.1); box-shadow: 0 0 20px rgba(79,172,254,0.6); }
        #tree-container { width: 100vw; height: calc(100vh - 220px); }
        .node circle { stroke: steelblue; stroke-width: 3px; }
        .node text { font: 15px sans-serif; cursor: pointer; fill: white; font-weight: 500; }
        .link { fill: none; stroke: #ccc; stroke-width: 2.5px; }
        #details {
            position: fixed; right: 20px; top: 240px; width: 380px; max-height: calc(100vh - 260px);
            background: rgba(0,0,0,0.7); padding: 25px; border-radius: 15px; overflow-y: auto;
            backdrop-filter: blur(12px); box-shadow: 0 10px 40px rgba(0,0,0,0.5);
        }
        #details h3 { margin-top: 0; color: #4facfe; font-size: 1.4em; }
        pre { white-space: pre-wrap; font-size: 1em; line-height: 1.5; }
        .badge { font-size: 0.85em; padding: 4px 10px; border-radius: 20px; margin-left: 10px; color: white; font-weight: bold; }
        .badge-brain-capacity { background: #764ba2; }
        .badge-knowledge { background: #f5576c; }
        .badge-intelligence { background: #00f2fe; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎨 System Code Visualizer</h1>
        <p>Interactive Horizontal Tree Explorer — Highly Readable</p>
        <div class="stats">%s</div>
        <div class="controls">
            <input type="text" id="search" class="search" placeholder="🔍 Search functions, classes, parameters, docstrings...">
            <div class="filters">
                <button class="filter-btn active" data-filter="all">All Components</button>
                <button class="filter-btn" data-filter="Brain Capacity">Brain Capacity</button>
                <button class="filter-btn" data-filter="Knowledge">Knowledge</button>
                <button class="filter-btn" data-filter="Intelligence">Intelligence</button>
            </div>
        </div>
    </div>

    <div id="tree-container"></div>
    <div id="details">
        <h3>👆 Click any node to explore</h3>
        <p>Expand modules → classes → methods. Full parameters, returns, and docstrings appear here.</p>
    </div>

    <script>
        const data = %s;

        const margin = {top: 50, right: 400, bottom: 50, left: 180};
        const width = window.innerWidth - margin.left - margin.right;
        const height = window.innerHeight - margin.top - margin.bottom - 220;

        const root = d3.hierarchy(data);
        root.x0 = height / 2;
        root.y0 = 0;

        const svg = d3.select("#tree-container")
            .append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom);

        const g = svg.append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

        const treeLayout = d3.tree()
            .size([height, width]);

        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on("zoom", (event) => g.attr("transform", event.transform));

        svg.call(zoom);

        let i = 0;
        const duration = 750;

        function update(source) {
            const treeData = treeLayout(root);
            const nodes = treeData.descendants();
            const links = treeData.links();

            // Horizontal: deeper = further right
            nodes.forEach(d => d.y = d.depth * 300);

            const node = g.selectAll(".node")
                .data(nodes, d => d.id || (d.id = ++i));

            const nodeEnter = node.enter().append("g")
                .attr("class", "node")
                .attr("transform", d => `translate(${source.y0},${source.x0})`)
                .on("click", clicked);

            nodeEnter.append("circle")
                .attr("r", 10)
                .style("fill", d => {
                    if (d.data.classification) {
                        if (d.data.classification.includes("Capacity")) return "#764ba2";
                        if (d.data.classification.includes("Knowledge")) return "#f5576c";
                        if (d.data.classification.includes("Intelligence")) return "#00f2fe";
                    }
                    return d.children ? "#667eea" : "#43e97b";
                })
                .style("stroke", "#fff")
                .style("stroke-width", "2px");

            nodeEnter.append("text")
                .attr("dy", "0.35em")
                .attr("x", d => d.children ? -20 : 20)
                .attr("text-anchor", d => d.children ? "end" : "start")
                .text(d => d.data.name)
                .style("font-weight", "600");

            // Badge
            nodeEnter.filter(d => d.data.badge)
                .append("text")
                .attr("dy", "0.35em")
                .attr("x", d => d.children ? -20 - (d.data.name.length * 8) - 20 : 20)
                .attr("text-anchor", d => d.children ? "end" : "start")
                .text(d => d.data.badge)
                .attr("class", d => "badge badge-" + d.data.badge.toLowerCase().replace(/ /g, "-"));

            const nodeUpdate = nodeEnter.merge(node)
                .transition()
                .duration(duration)
                .attr("transform", d => `translate(${d.y},${d.x})`);

            const nodeExit = node.exit()
                .transition()
                .duration(duration)
                .attr("transform", d => `translate(${source.y},${source.x})`)
                .remove();

            nodeExit.select("circle").attr("r", 1e-6);
            nodeExit.selectAll("text").style("fill-opacity", 1e-6);

            const link = g.selectAll(".link")
                .data(links, d => d.target.id);

            const linkEnter = link.enter().insert("path", "g")
                .attr("class", "link")
                .attr("d", d => {
                    const o = {x: source.x0, y: source.y0};
                    return diagonal(o, o);
                });

            linkEnter.merge(link)
                .transition()
                .duration(duration)
                .attr("d", diagonal);

            link.exit().transition().duration(duration).remove();

            nodes.forEach(d => { d.x0 = d.x; d.y0 = d.y; });
        }

        function diagonal(s, d) {
            return `M ${s.y} ${s.x}
                    C ${(s.y + d.y) / 2} ${s.x},
                      ${(s.y + d.y) / 2} ${d.x},
                      ${d.y} ${d.x}`;
        }

        function clicked(event, d) {
            if (d.children) {
                d._children = d.children;
                d.children = null;
            } else {
                d.children = d._children;
                d._children = null;
            }
            update(d);

            let badgeHTML = "";
            if (d.data.badge) {
                badgeHTML = `<span class="badge badge-${d.data.badge.toLowerCase().replace(/ /g, "-")}">${d.data.badge}</span><br><br>`;
            }

            const detailsHTML = `
                <h3>${d.data.name}</h3>
                ${badgeHTML}
                <pre>${d.data.details || "No additional details available."}</pre>
            `;
            d3.select("#details").html(detailsHTML);
        }

        update(root);

        // Auto-fit zoom to show entire tree on load
        const bounds = g.node().getBBox();
        const fullWidth = bounds.width + margin.left + margin.right;
        const fullHeight = bounds.height + margin.top + margin.bottom;
        const scale = Math.min(
            (window.innerWidth * 0.95) / fullWidth,
            (window.innerHeight * 0.85) / fullHeight
        );
        const translate = [
            (window.innerWidth - fullWidth * scale) / 2,
            (window.innerHeight - fullHeight * scale) / 2 + 50
        ];
        svg.transition().duration(1000).call(zoom.transform, d3.zoomIdentity.translate(...translate).scale(scale));

        // Search
        d3.select("#search").on("input", function() {
            const term = this.value.toLowerCase();
            g.selectAll(".node text")
                .style("font-weight", d => (d.data.name + " " + (d.data.details || "")).toLowerCase().includes(term) ? "900" : "500")
                .style("fill", d => (d.data.name + " " + (d.data.details || "")).toLowerCase().includes(term) ? "#ffd700" : "white");
        });

        // Filter
        d3.selectAll(".filter-btn").on("click", function() {
            d3.selectAll(".filter-btn").classed("active", false);
            d3.select(this).classed("active", true);
            const filter = this.getAttribute("data-filter");

            g.selectAll(".node circle, .node text")
                .style("opacity", d => {
                    if (filter === "all") return 1;
                    if (!d.data.classification) return 0.3;
                    return d.data.classification === filter ? 1 : 0.3;
                });
        });
    </script>
</body>
</html>"""

        return html_template % (stats_html, hierarchy_json)


if __name__ == "__main__":
    print("="*80)
    print("INTERACTIVE CODE VISUALIZER - HORIZONTAL READABLE EDITION")
    print("Perfect for large systems and presentations")
    print("="*80)
    
    visualizer = CodeVisualizer("/app")
    visualizer.generate_interactive_html("/app/code_visualizer.html")
    
    print("\n" + "="*80)
    print("✓ VISUALIZATION COMPLETE - OPEN code_visualizer.html")
    print("   → Now with clean horizontal layout and auto-fit zoom!")
    print("="*80)