import os

# GA4 tag and CSS overrides to inject
INJECT_CONTENT = """
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-3JQ48J80W0"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', 'G-3JQ48J80W0');
</script>

<!-- Font Settings for Web -->
<style>
  :lang(en) {
    font-family: "Roboto", "Helvetica", "Arial", sans-serif;
  }
</style>
"""

# Path to the Pygbag output file
INDEX_PATH = os.path.join("build", "web", "index.html")

def inject_ga4():
    if not os.path.exists(INDEX_PATH):
        print(f"Error: {INDEX_PATH} not found. Build the project first.")
        return

    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Inject before </head>
    if "</head>" in content:
        new_content = content.replace("</head>", f"{INJECT_CONTENT}\n</head>")
        
        # Replace loading text
        new_content = new_content.replace('Ready to start !', 'Click to continue')
        
        # Add timeout to UME wait loop (10 second timeout)
        old_loop = '''        while not platform.window.MM.UME:
            await asyncio.sleep(.1)'''
        new_loop = '''        timeout = 100  # 10 seconds
        while not platform.window.MM.UME and timeout > 0:
            await asyncio.sleep(.1)
            timeout -= 1'''
        new_content = new_content.replace(old_loop, new_loop)
        
        # Update page title
        new_content = new_content.replace('<title>woodpazzule</title>', '<title>ウッドパズル ― 無料ゲーム | Wood Puzzle - Free Game</title>')
        
        with open(INDEX_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"Successfully injected GA4 tag into {INDEX_PATH}")
        print(f"Updated loading text to 'Now Loading...'")
    else:
        print("Error: Could not find </head> tag in index.html")

if __name__ == "__main__":
    inject_ga4()
