import os
import glob

STAGES_DIR = r"c:\Users\masa7\Antigravity\woodpazzule\stages"
OUTPUT_FILE = r"c:\Users\masa7\Antigravity\woodpazzule\stages.md"

def parse_stage_file(filepath):
    data = {}
    current_section = None
    grid_lines = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                if line.startswith('# GRID'):
                    current_section = 'grid'
                continue
            
            if ':' in line and current_section != 'grid' and 'piece' not in line:
                key, value = line.split(':', 1)
                data[key.strip()] = value.strip()
            
            elif current_section == 'grid' and ('0' in line or '1' in line):
                grid_lines.append(line)
    
    data['grid'] = grid_lines
    return data

def generate_markdown():
    stage_files = sorted(glob.glob(os.path.join(STAGES_DIR, "STAGE_*.stage")))
    
    md_lines = ["# ステージ一覧", "", "| ID | Name | Difficulty | Shape (Preview) |", "|---|---|---|---|"]
    
    for filepath in stage_files:
        filename = os.path.basename(filepath)
        data = parse_stage_file(filepath)
        
        stage_id = data.get('stage_id', 'Unknown')
        name = data.get('name', 'Unknown')
        difficulty = data.get('difficulty', '-')
        
        # Simple grid preview (mini)
        # Convert 1 to '■', 0 to ' ' for a tiny view, maybe just the first few lines or a description
        # Since markdown table cells can't handle multiline well without <br>, let's try to make a compact representation
        # Or just describe it.
        # Actually, let's just make a separate section for each stage if we want full ASCII art.
        # But the user asked for "characteristics record". A table is good for summary.
        
        # Let's compress the grid to a single line visual? No, that's hard.
        # Let's just output text.
        
        md_lines.append(f"| {stage_id} | {name} | {difficulty} | (See details below) |")

    md_lines.append("")
    md_lines.append("## 詳細")
    
    for filepath in stage_files:
        data = parse_stage_file(filepath)
        filename = os.path.basename(filepath)
        
        md_lines.append(f"### {data.get('stage_id')} - {data.get('name')}")
        md_lines.append(f"- **Difficulty**: {data.get('difficulty')}")
        md_lines.append(f"- **Filename**: `{filename}`")
        md_lines.append("")
        md_lines.append("```")
        for line in data.get('grid', []):
            # Replace 1 with #, 0 with . for better visibility
            visual = line.replace('1', '■').replace('0', '□').replace(' ', '')
            md_lines.append(visual)
        md_lines.append("```")
        md_lines.append("")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))
    
    print(f"Generated {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_markdown()
