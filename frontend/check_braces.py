
def check_braces(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    stack = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        for j, char in enumerate(line):
            if char in '{[(':
                stack.append((char, i + 1, j + 1))
            elif char in '}])':
                if not stack:
                    print(f"Error: Unexpected {char} at line {i+1} col {j+1}")
                    return
                
                last, li, lj = stack.pop()
                if (last == '{' and char != '}') or \
                   (last == '[' and char != ']') or \
                   (last == '(' and char != ')'):
                    print(f"Error: Mismatched {last} at {li}:{lj} with {char} at {i+1}:{j+1}")
                    return

    if stack:
        last, li, lj = stack[-1]
        print(f"Error: Unclosed {last} at line {li} col {lj}")
    else:
        print("Braces are balanced.")

check_braces('/Users/badraaji/Desktop/RND/saham-indo/frontend/src/components/BrokerSummaryPanel.jsx')
