
import re

def check_structure(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    # Check braces first (redundant but safe)
    stack = []
    
    # Check Tags
    tag_stack = []
    
    # Simple regex for tags: <TagName> or </TagName> or <TagName />
    # We care about div, Fragment (<>), etc.
    # Ignores attributes for simplicity
    
    # Simplify content: remove {} blocks? No, tags can be inside.
    # This is complex to parse perfectly without a parser.
    # Use simple stack for strict matching of simplified tokens.
    
    print("Checking tag balance (simplified)...")
    
    # Find all tags
    # matches: (is_closing, tag_name, is_self_closing)
    # <div ... > -> (False, "div", False)
    # </div> -> (True, "div", False)
    # <div ... /> -> (False, "div", True)
    # <> -> (False, "", False)
    # </> -> (True, "", False)
    
    regex = re.compile(r'<(/?)(\w*)[^>]*?(/?)>')
    
    for i, line in enumerate(lines):
        # Remove comments logic is hard, skipping
        matches = regex.finditer(line)
        for match in matches:
            full_match = match.group(0)
            is_closing_slash = match.group(1) == '/'
            tag_name = match.group(2)
            is_self_closing_slash = match.group(3) == '/'
            
            if "BrokerDetailModal" in tag_name: continue # Assume self closing or handled
            if "ChartTooltip" in tag_name: continue
            if "XAxis" in tag_name: continue
            if "YAxis" in tag_name: continue
            if "CartesianGrid" in tag_name: continue
            if "Area" in tag_name: continue
            if "Line" in tag_name: continue
            if "Defs" in tag_name: continue
            if "Stop" in tag_name: continue
            if "Legend" in tag_name: continue
            if "GridIcon" in tag_name: continue
            if "Activity" in tag_name: continue
            if "BarChart2" in tag_name: continue
            if "Building2" in tag_name: continue
            if "RefreshCw" in tag_name: continue
            if "ArrowUpRight" in tag_name: continue
            if "ArrowDownRight" in tag_name: continue
            if "Users" in tag_name: continue
            if "TrendingUp" in tag_name: continue
            if "TrendingDown" in tag_name: continue
            if "Minus" in tag_name: continue
            if "Calendar" in tag_name: continue
            if "Upload" in tag_name: continue
            if "TypeBadge" in tag_name: continue
            if "BrokerRow" in tag_name: continue # Custom components often self-closing inputs? 
            # BrokerRow is NOT self closing in mapping? No, <BrokerRow ... /> is self closing.
            # But the regex might capture it.
            
            if is_self_closing_slash:
                continue
            
            if tag_name in ['img', 'input', 'br', 'hr']: # Void elements
                continue

            if is_closing_slash:
                if not tag_stack:
                    print(f"Error: Unexpected closing </{tag_name}> at line {i+1}")
                    return
                last_tag = tag_stack.pop()
                if last_tag != tag_name:
                    print(f"Error: Mismatched tag. Expected </{last_tag}> but got </{tag_name}> at line {i+1}")
                    return
            else:
                tag_stack.append(tag_name)

    if tag_stack:
        print(f"Error: Unclosed tags remaining: {tag_stack}")
    else:
        print("Tags appear balanced.")

check_structure('/Users/badraaji/Desktop/RND/saham-indo/frontend/src/components/BrokerSummaryPanel.jsx')
