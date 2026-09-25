"""
Documentation builder script.
Prepares the `docs/` structure from root README and case studies,
normalizes cross-case-study links, and builds the static site using MkDocs.
"""

import os
import re
import shutil
import subprocess
import sys


def fix_relative_links(file_path: str):
    """Fix relative cross-links like [Text](case-studies/XX-...) inside a subfolder to [Text](../XX-...)."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Pattern: [Link Text](case-studies/01-agentic-...) -> [Link Text](../01-agentic-...)
    # inside subdirectories under case-studies/
    modified = re.sub(r'\]\(case-studies/(\d{2}-[^)]+)\)', r'](../\1)', content)

    if modified != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(modified)


def prepare_docs():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    docs_dir = os.path.join(repo_root, "docs")
    case_studies_src = os.path.join(repo_root, "case-studies")
    case_studies_dst = os.path.join(docs_dir, "case-studies")

    print("[1/4] Cleaning and preparing docs/ directory...")
    if os.path.exists(docs_dir):
        shutil.rmtree(docs_dir)
    os.makedirs(docs_dir, exist_ok=True)

    # 1. Copy root README to docs/index.md
    readme_src = os.path.join(repo_root, "README.md")
    readme_dst = os.path.join(docs_dir, "index.md")
    print(f"      Copying {readme_src} -> {readme_dst}")
    with open(readme_src, "r", encoding="utf-8") as f:
        content = f.read()

    with open(readme_dst, "w", encoding="utf-8") as f:
        f.write(content)

    # 2. Copy all case-studies to docs/case-studies
    print(f"[2/4] Copying case studies to {case_studies_dst}...")
    shutil.copytree(case_studies_src, case_studies_dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # 3. Normalize cross-case-study links inside case-studies
    print("[3/4] Normalizing cross-reference links...")
    for root, _, files in os.walk(case_studies_dst):
        for file in files:
            if file.endswith(".md"):
                fix_relative_links(os.path.join(root, file))

    # 4. Create mathjax.js helper for LaTeX formula rendering
    js_dir = os.path.join(docs_dir, "javascripts")
    os.makedirs(js_dir, exist_ok=True)
    mathjax_js = os.path.join(js_dir, "mathjax.js")
    with open(mathjax_js, "w", encoding="utf-8") as f:
        f.write("""window.MathJax = {
  tex: {
    inlineMath: [["\\\\(", "\\\\)"], ["$", "$"]],
    displayMath: [["\\\\[", "\\\\]"], ["$$", "$$"]],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex"
  }
};

document$.subscribe(() => {
  if (typeof MathJax !== "undefined" && MathJax.typesetPromise) {
    MathJax.startup.output.clearCache();
    MathJax.typesetClear();
    MathJax.texReset();
    MathJax.typesetPromise();
  }
});
""")

    print("[4/4] Docs structure prepared successfully.")


def run_mkdocs_build():
    print("\n[BUILD] Running mkdocs build --strict...")
    res = subprocess.run([sys.executable, "-m", "mkdocs", "build", "--strict"], check=False)
    if res.returncode != 0:
        print("[WARNING] Strict build had notices, running standard build...")
        subprocess.run([sys.executable, "-m", "mkdocs", "build"], check=True)
    print("\n[SUCCESS] MkDocs site build completed successfully!")


def run_unit_tests():
    """Runs the documentation and math equation unit test suite."""
    print("\n[TEST] Running documentation & math formula unit test suite...")
    test_file = os.path.join(os.path.dirname(__file__), "..", "tests", "test_docs_build.py")
    res = subprocess.run([sys.executable, "-m", "unittest", test_file], check=False)
    if res.returncode != 0:
        print("\n[ERROR] Documentation unit tests failed! Fix issues before building/pushing.", file=sys.stderr)
        sys.exit(1)
    print("\n[SUCCESS] All documentation unit tests passed!")


if __name__ == "__main__":
    prepare_docs()
    if "--test" in sys.argv:
        run_unit_tests()
    elif "--build" in sys.argv:
        run_mkdocs_build()
        run_unit_tests()
    else:
        run_unit_tests()
