"""
SYSTEM FLOWCHART GENERATOR
Generate visual architecture from documentation

SUPERVISOR'S REQUIREMENT:
"With function list, I can create flowchart.
 Then we know where to put new features."
"""

import json
from typing import Dict, List, Any
from pathlib import Path


class FlowchartGenerator:
    """
    Generates visual flowchart from system documentation
    
    SUPERVISOR'S FRAMEWORK:
    - Brain Capacity (what system can do)
    - Knowledge (what system knows)
    - Intelligence (how system uses capacity + knowledge)
    """
    
    def __init__(self, doc_json_path: str):
        """Load documentation JSON"""
        with open(doc_json_path, 'r') as f:
            self.doc = json.load(f)
    
    def generate_mermaid(self, output_path: str):
        """
        Generate Mermaid flowchart
        
        Supervisor: "Flowchart shows clear boundaries between components"
        """
        mermaid = []
        
        # Header
        mermaid.append("```mermaid")
        mermaid.append("graph TB")
        mermaid.append("")
        
        # Main architecture layers
        mermaid.append("  %% SUPERVISOR'S ARCHITECTURE")
        mermaid.append("  subgraph CAPACITY[\"BRAIN CAPACITY - What System CAN Do\"]")
        mermaid.append("    TS[Timestamp Manager<br/>Internal Time]")
        mermaid.append("    SM[State Manager<br/>Current/Previous State]")
        mermaid.append("    MH[Memory Handler<br/>Short/Long Term]")
        mermaid.append("  end")
        mermaid.append("")
        
        mermaid.append("  subgraph KNOWLEDGE[\"KNOWLEDGE - What System KNOWS\"]")
        mermaid.append("    KG[Knowledge Graphs<br/>All Tried Paths]")
        mermaid.append("    BC[Brain Core<br/>Actions/Feedbacks]")
        mermaid.append("  end")
        mermaid.append("")
        
        mermaid.append("  subgraph INTELLIGENCE[\"INTELLIGENCE - How System USES\"]")
        mermaid.append("    AW[Awareness<br/>Knowledge vs Reality]")
        mermaid.append("    RP[Repeat<br/>Query Knowledge]")
        mermaid.append("    EX[Explore<br/>Try New Actions]")
        mermaid.append("    FC[Future Constraints<br/>Goal Validation]")
        mermaid.append("  end")
        mermaid.append("")
        
        mermaid.append("  subgraph ENVIRONMENT[\"ENVIRONMENT - External\"]")
        mermaid.append("    TM[TrackMania<br/>Episodes/Frames]")
        mermaid.append("    FB[Feedback<br/>Sensors]")
        mermaid.append("  end")
        mermaid.append("")
        
        # Connections
        mermaid.append("  %% Information Flow")
        mermaid.append("  TM -->|Feedback| FB")
        mermaid.append("  FB -->|Observations| BC")
        mermaid.append("  BC -->|Record| KG")
        mermaid.append("  BC -->|Track| SM")
        mermaid.append("  SM -->|History| MH")
        mermaid.append("")
        
        mermaid.append("  %% Intelligence Flow")
        mermaid.append("  KG -->|Predict| AW")
        mermaid.append("  FB -->|Actual| AW")
        mermaid.append("  AW -->|Validation Code| BC")
        mermaid.append("  KG -->|Query| RP")
        mermaid.append("  KG -->|Check Coverage| EX")
        mermaid.append("  SM -->|Future State| FC")
        mermaid.append("")
        
        # Styling
        mermaid.append("  %% Styling")
        mermaid.append("  classDef capacity fill:#e1f5ff,stroke:#01579b")
        mermaid.append("  classDef knowledge fill:#fff9c4,stroke:#f57f17")
        mermaid.append("  classDef intelligence fill:#f3e5f5,stroke:#4a148c")
        mermaid.append("  classDef environment fill:#ffebee,stroke:#b71c1c")
        mermaid.append("")
        
        mermaid.append("  class TS,SM,MH capacity")
        mermaid.append("  class KG,BC knowledge")
        mermaid.append("  class AW,RP,EX,FC intelligence")
        mermaid.append("  class TM,FB environment")
        
        mermaid.append("```")
        
        # Write to file
        with open(output_path, 'w') as f:
            f.write("\n".join(mermaid))
        
        print(f"✓ Mermaid flowchart generated: {output_path}")
    
    def generate_detailed_markdown(self, output_path: str):
        """
        Generate detailed architecture documentation
        
        Includes all functions with classifications
        """
        md = []
        
        md.append("# System Architecture - Detailed")
        md.append("")
        md.append("## Supervisor's Framework")
        md.append("")
        md.append("### Brain Capacity (What System CAN Do)")
        md.append("God-given abilities - what system is capable of")
        md.append("")
        
        md.append("### Knowledge (What System KNOWS)")
        md.append("Data stored - all tried paths and outcomes")
        md.append("")
        
        md.append("### Intelligence (How System USES)")
        md.append("Using capacity + knowledge to make decisions")
        md.append("")
        
        md.append("---")
        md.append("")
        
        # Group by classification
        capacity_files = []
        knowledge_files = []
        intelligence_files = []
        unclassified_files = []
        
        for file_doc in self.doc['files']:
            has_capacity = False
            has_knowledge = False
            has_intelligence = False
            
            for class_doc in file_doc['classes']:
                if class_doc['classification'] == 'Brain Capacity':
                    has_capacity = True
                elif class_doc['classification'] == 'Knowledge':
                    has_knowledge = True
                elif class_doc['classification'] == 'Intelligence':
                    has_intelligence = True
            
            if has_capacity:
                capacity_files.append(file_doc)
            if has_knowledge:
                knowledge_files.append(file_doc)
            if has_intelligence:
                intelligence_files.append(file_doc)
            if not (has_capacity or has_knowledge or has_intelligence):
                unclassified_files.append(file_doc)
        
        # Document each category
        md.append("## Brain Capacity Components")
        md.append("")
        for file_doc in capacity_files:
            md.extend(self._document_file(file_doc, "Brain Capacity"))
        
        md.append("## Knowledge Components")
        md.append("")
        for file_doc in knowledge_files:
            md.extend(self._document_file(file_doc, "Knowledge"))
        
        md.append("## Intelligence Components")
        md.append("")
        for file_doc in intelligence_files:
            md.extend(self._document_file(file_doc, "Intelligence"))
        
        # Write to file
        with open(output_path, 'w') as f:
            f.write("\n".join(md))
        
        print(f"✓ Detailed architecture generated: {output_path}")
    
    def _document_file(self, file_doc: Dict, filter_class: str) -> List[str]:
        """Document single file filtered by classification"""
        lines = []
        
        lines.append(f"### {file_doc['filepath']}")
        lines.append("")
        
        for class_doc in file_doc['classes']:
            if class_doc['classification'] == filter_class:
                lines.append(f"#### {class_doc['name']}")
                lines.append(f"*{class_doc['classification']}*")
                lines.append("")
                lines.append(f"> {class_doc['docstring']}")
                lines.append("")
                
                if class_doc['methods']:
                    lines.append("**Key Methods:**")
                    for method in class_doc['methods'][:5]:  # Top 5 methods
                        lines.append(f"- `{method['signature']}`")
                    lines.append("")
        
        return lines
    
    def generate_component_list(self, output_path: str):
        """
        Generate simple component list
        
        Supervisor: "List all folders, files, classes, functions"
        """
        lines = []
        
        lines.append("# System Components List")
        lines.append("")
        lines.append(f"Total Files: {self.doc['system_overview']['total_files']}")
        lines.append(f"Total Classes: {self.doc['system_overview']['total_classes']}")
        lines.append(f"Total Functions: {self.doc['system_overview']['total_functions']}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        for file_doc in self.doc['files']:
            lines.append(f"## {file_doc['filepath']}")
            lines.append("")
            
            for class_doc in file_doc['classes']:
                lines.append(f"### {class_doc['name']} - *{class_doc['classification']}*")
                lines.append("")
                
                for method in class_doc['methods']:
                    lines.append(f"- `{method['signature']}`")
                lines.append("")
        
        with open(output_path, 'w') as f:
            f.write("\n".join(lines))
        
        print(f"✓ Component list generated: {output_path}")


# ============================================================================
# USAGE
# ============================================================================

if __name__ == "__main__":
    # Load documentation
    generator = FlowchartGenerator("/app/system_documentation.json")
    
    # Generate flowchart
    generator.generate_mermaid("/app/SYSTEM_FLOWCHART.md")
    
    # Generate detailed docs
    generator.generate_detailed_markdown("/app/ARCHITECTURE_DETAILED.md")
    
    # Generate component list
    generator.generate_component_list("/app/COMPONENTS_LIST.md")
    
    print("\n" + "="*80)
    print("✓ ALL DOCUMENTATION GENERATED")
    print("="*80)