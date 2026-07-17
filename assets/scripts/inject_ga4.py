import os
import re

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

# Source of truth for the app version
VERSION_PATH = os.path.join("src", "__init__.py")


def read_version():
    """
    src/__init__.py の __version__ を読む

    公開されている版が新しいか古いかをタブのタイトルで見分けられるようにするため、
    タイトルへ差し込む。import せず正規表現で読むのは、このスクリプトが
    pygame等に依存せず単体で動くようにするため。
    """
    try:
        with open(VERSION_PATH, 'r', encoding='utf-8') as f:
            m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', f.read(), re.M)
        if m:
            return m.group(1)
        print(f"Warning: __version__ not found in {VERSION_PATH}")
    except OSError as e:
        print(f"Warning: could not read {VERSION_PATH}: {e}")
    return None


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
        
        # Update page title (バージョン付き: 公開版の新旧を人が見分けられるように)
        version = read_version()
        title = 'ウッドパズル ― 無料ゲーム | Wood Puzzle - Free Game'
        if version:
            title += f' (ver {version})'
        new_content = new_content.replace('<title>woodpazzule</title>', f'<title>{title}</title>')

        with open(INDEX_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"Successfully injected GA4 tag into {INDEX_PATH}")
        print(f"Updated loading text to 'Now Loading...'")
        print(f"Page title: {title}")
    else:
        print("Error: Could not find </head> tag in index.html")

if __name__ == "__main__":
    inject_ga4()
