"""
Generic, Automated Unit Test Suite for Agentic-AI-Case-Studies.
================================================================
Validates all existing (01-29) and future (30+) case studies:
  1. Directory & File Structure (slug naming, README.md, H1 title, links, code fences).
  2. Index & Registry Synchronization (root README table/tree, mkdocs.yml nav).
  3. Character Encoding & Integrity (UTF-8, no replacement chars U+FFFD).
  4. LaTeX & MathJax Syntax (isolated $$, no raw < / > in math mode, no unsupported macros).
  5. Mermaid Diagram Robustness (valid headers, quoted edge labels, no raw <think> tags).
  6. Static Site HTML Build Integrity (no dangling dollars, no misplaced entities).

Executed automatically by the Git pre-push hook (.git/hooks/pre-push).
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CASE_STUDIES_DIR = os.path.join(REPO_ROOT, "case-studies")
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
SITE_DIR = os.path.join(REPO_ROOT, "site")
ROOT_README = os.path.join(REPO_ROOT, "README.md")
MKDOCS_YML = os.path.join(REPO_ROOT, "mkdocs.yml")


def get_all_case_study_dirs():
    """Dynamically returns all numbered case study directories sorted numerically."""
    return sorted(
        [
            d for d in os.listdir(CASE_STUDIES_DIR)
            if os.path.isdir(os.path.join(CASE_STUDIES_DIR, d)) and re.match(r"^\d{2}-", d)
        ],
        key=lambda x: int(x.split("-")[0])
    )


# ============================================================================
# 1. Generic Case Study Structure & Markdown Integrity
# ============================================================================

class TestCaseStudyStructure(unittest.TestCase):
    """Generic structural and integrity tests across all present and future case studies."""

    def test_case_study_directory_naming_convention(self):
        """Every case study directory must strictly follow 'NN-lowercase-hyphenated-slug' format."""
        pattern = re.compile(r"^\d{2}-[a-z0-9]+(-[a-z0-9]+)*$")
        all_dirs = get_all_case_study_dirs()
        self.assertGreaterEqual(len(all_dirs), 1, "At least one case study must exist")

        invalid = [d for d in all_dirs if not pattern.match(d)]
        self.assertEqual(
            invalid,
            [],
            f"Case study directory names do not follow 'NN-lowercase-slug' format: {invalid}",
        )

    def test_case_study_readme_exists_and_non_empty(self):
        """Every case study directory must contain a non-trivial README.md (> 200 bytes)."""
        all_dirs = get_all_case_study_dirs()
        for d in all_dirs:
            readme_path = os.path.join(CASE_STUDIES_DIR, d, "README.md")
            self.assertTrue(os.path.exists(readme_path), f"Missing README.md in {d}")
            self.assertGreater(
                os.path.getsize(readme_path),
                200,
                f"README.md in {d} is suspiciously small or empty",
            )

    def test_case_study_h1_title_convention(self):
        """First non-empty line of every case study README must match '# Case Study <NN>: ...'."""
        all_dirs = get_all_case_study_dirs()
        violations = []

        for d in all_dirs:
            readme_path = os.path.join(CASE_STUDIES_DIR, d, "README.md")
            num_str = d.split("-")[0]
            expected_prefix = rf"^# Case Study (?:{num_str}|{int(num_str)}):"

            with open(readme_path, "r", encoding="utf-8") as f:
                first_line = ""
                for line in f:
                    if line.strip():
                        first_line = line.strip()
                        break

            if not re.match(expected_prefix, first_line):
                violations.append(f"{d}: found '{first_line[:40]}...', expected prefix '# Case Study {num_str}:'")

        self.assertEqual(
            violations,
            [],
            "Case study READMEs with missing or mismatched H1 title prefix:\n" + "\n".join(violations),
        )

    def test_no_broken_relative_links(self):
        """All relative links [Text](path) outside code blocks must resolve to existing files on disk."""
        all_dirs = get_all_case_study_dirs()
        broken_links = []

        for d in all_dirs:
            readme_path = os.path.join(CASE_STUDIES_DIR, d, "README.md")
            with open(readme_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Strip code blocks to avoid matching python code indexing e.g. tools[name](**args)
            no_code = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
            no_code = re.sub(r"`[^`\n]+`", "", no_code)

            links = re.findall(r"\[([^\]]+)\]\(([^)#\s][^)]*)\)", no_code)
            for text, url in links:
                # Ignore external URLs and mailto
                if url.startswith(("http://", "https://", "mailto:", "ftp://")):
                    continue
                # Remove query params or anchors if any
                clean_url = url.split("?")[0].split("#")[0]
                if not clean_url:
                    continue
                target = os.path.normpath(os.path.join(CASE_STUDIES_DIR, d, clean_url))
                if not os.path.exists(target):
                    broken_links.append(f"{d}: [{text}]({url}) -> unresolved '{target}'")

        self.assertEqual(
            broken_links,
            [],
            "Found broken relative links in case study markdown files:\n" + "\n".join(broken_links),
        )

    def test_markdown_code_fences_balanced(self):
        """Every case study README must have an even count of code fences (no unclosed ```)."""
        all_dirs = get_all_case_study_dirs()
        unbalanced = []

        for d in all_dirs:
            readme_path = os.path.join(CASE_STUDIES_DIR, d, "README.md")
            with open(readme_path, "r", encoding="utf-8") as f:
                content = f.read()

            fences = len(re.findall(r"^```", content, re.MULTILINE))
            if fences % 2 != 0:
                unbalanced.append(f"{d}: found {fences} fence markers (must be even)")

        self.assertEqual(
            unbalanced,
            [],
            "Found unbalanced markdown code fences in case studies:\n" + "\n".join(unbalanced),
        )


# ============================================================================
# 2. Registry & Synchronization Tests (Root README & mkdocs.yml)
# ============================================================================

class TestRegistryAndNavigationSync(unittest.TestCase):
    """Ensures root README and mkdocs.yml stay 100% in sync as new case studies are added."""

    def test_mkdocs_nav_includes_all_case_studies(self):
        """Every case study README in case-studies/ must be registered in mkdocs.yml nav."""
        self.assertTrue(os.path.exists(MKDOCS_YML), "mkdocs.yml must exist")
        with open(MKDOCS_YML, "r", encoding="utf-8") as f:
            content = f.read()

        missing = []
        all_dirs = get_all_case_study_dirs()
        for d in all_dirs:
            expected_ref = f"case-studies/{d}/README.md"
            if expected_ref not in content:
                missing.append(expected_ref)

        self.assertEqual(
            missing,
            [],
            f"Missing case studies in mkdocs.yml nav configuration:\n" + "\n".join(missing),
        )

    def test_root_readme_index_table_includes_all_case_studies(self):
        """Root README.md Case Studies Index table must list every case study directory."""
        self.assertTrue(os.path.exists(ROOT_README), "Root README.md must exist")
        with open(ROOT_README, "r", encoding="utf-8") as f:
            content = f.read()

        missing = []
        all_dirs = get_all_case_study_dirs()
        for d in all_dirs:
            expected_ref = f"case-studies/{d}/README.md"
            if expected_ref not in content:
                missing.append(f"{d} (missing link: {expected_ref})")

        self.assertEqual(
            missing,
            [],
            "Case studies missing from root README.md index table:\n" + "\n".join(missing),
        )

    def test_root_readme_directory_tree_includes_all_case_studies(self):
        """Root README.md folder tree diagram must list every case study folder."""
        with open(ROOT_README, "r", encoding="utf-8") as f:
            content = f.read()

        missing = []
        all_dirs = get_all_case_study_dirs()
        for d in all_dirs:
            if d not in content:
                missing.append(d)

        self.assertEqual(
            missing,
            [],
            "Case study directory names missing from root README.md directory tree:\n" + "\n".join(missing),
        )


# ============================================================================
# 3. LaTeX & MathJax Syntax Guardrails
# ============================================================================

class TestMarkdownMathSyntax(unittest.TestCase):
    """Generic LaTeX and MathJax validation for all current and future case studies."""

    def test_no_indented_display_math_blocks(self):
        """Display math ($$) must not be indented under list items, which breaks GitHub and arithmatex."""
        indented_pattern = re.compile(r"^\s+\$\$(?!.*<!--)")
        violations = []

        for root, _, files in os.walk(CASE_STUDIES_DIR):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            if indented_pattern.match(line):
                                violations.append(f"{rel_path}:{line_num}: {line.strip()}")

        self.assertEqual(
            violations,
            [],
            f"Found indented display math ($$) blocks which break renderer:\n" + "\n".join(violations),
        )

    def test_matching_display_math_delimiters(self):
        """Every display math block ($$) must have matching delimiters on isolated lines."""
        for root, _, files in os.walk(CASE_STUDIES_DIR):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()

                    isolated_count = len(re.findall(r"^\s*\$\$\s*$", content, re.MULTILINE))
                    self.assertEqual(
                        isolated_count % 2,
                        0,
                        f"Unpaired display math $$ delimiters in {rel_path} (count: {isolated_count})",
                    )

    def test_no_raw_relational_operators_in_math_mode(self):
        """Inline math with relational operators must use \\gt / \\lt to avoid HTML entity encoding (&gt;)."""
        violations = []
        raw_rel_pattern = re.compile(r"\$[^\$\n]*?(?:\s+[><]\s+|>[0-9]|<[0-9])[^\$\n]*?\$")

        for root, _, files in os.walk(CASE_STUDIES_DIR):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        in_code_block = False
                        for line_num, line in enumerate(f, 1):
                            if line.strip().startswith("```"):
                                in_code_block = not in_code_block
                                continue
                            if in_code_block:
                                continue
                            if "flowchart" in line or "classDef" in line:
                                continue
                            if raw_rel_pattern.search(line):
                                violations.append(f"{rel_path}:{line_num}: {line.strip()}")

        self.assertEqual(
            violations,
            [],
            f"Found unescaped '>' or '<' in math mode (use \\gt / \\lt to prevent HTML escaping):\n" + "\n".join(violations),
        )

    def test_no_unsupported_mathjax_macros(self):
        """Macros like \\xrightleftharpoons from non-standard LaTeX packages must not be used."""
        unsupported = ["\\xrightleftharpoons"]
        violations = []
        for root, _, files in os.walk(CASE_STUDIES_DIR):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            for macro in unsupported:
                                if macro in line:
                                    violations.append(f"{rel_path}:{line_num}: {line.strip()}")
        self.assertEqual(
            violations,
            [],
            f"Found unsupported MathJax macros in markdown files (use standard \\overset/\\underset):\n" + "\n".join(violations),
        )

    def test_all_display_math_blocks_have_balanced_braces(self):
        """All display math blocks ($$...$$) across all case studies must have balanced curly braces."""
        violations = []
        for root, _, files in os.walk(CASE_STUDIES_DIR):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()

                    blocks = re.findall(r"\$\$(.*?)\$\$", content, re.DOTALL)
                    for idx, block in enumerate(blocks):
                        # Count braces ignoring escaped \{ and \}
                        clean_block = block.replace(r"\{", "").replace(r"\}", "")
                        open_count = clean_block.count("{")
                        close_count = clean_block.count("}")
                        if open_count != close_count:
                            violations.append(
                                f"{rel_path} (block {idx}): {open_count} open vs {close_count} close braces"
                            )

        self.assertEqual(
            violations,
            [],
            "Found unbalanced curly braces in display math blocks:\n" + "\n".join(violations),
        )


# ============================================================================
# 4. Mermaid Diagram Syntax & Robustness
# ============================================================================

class TestMermaidDiagramSyntax(unittest.TestCase):
    """Validates Mermaid diagrams in markdown files to ensure zero browser rendering syntax errors."""

    VALID_DIAGRAM_TYPES = (
        "graph",
        "flowchart",
        "sequenceDiagram",
        "classDiagram",
        "stateDiagram",
        "stateDiagram-v2",
        "erDiagram",
        "gitGraph",
        "gantt",
        "pie",
        "quadrantChart",
    )

    def test_mermaid_diagram_headers(self):
        """All mermaid blocks must declare a recognized valid diagram type header."""
        for root, _, files in os.walk(CASE_STUDIES_DIR):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()

                    mermaid_blocks = re.findall(r"```mermaid\n(.*?)\n```", content, re.DOTALL)
                    for idx, block in enumerate(mermaid_blocks):
                        lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
                        self.assertTrue(len(lines) > 0, f"Empty mermaid block {idx} in {rel_path}")
                        header = lines[0].split()[0]
                        self.assertIn(
                            header,
                            self.VALID_DIAGRAM_TYPES,
                            f"Invalid Mermaid diagram header '{header}' in {rel_path} (block {idx})",
                        )

    def test_no_unquoted_special_characters_in_mermaid_edge_labels(self):
        """Mermaid edge labels (|...|) must not contain unquoted brackets or parens that trigger syntax errors."""
        violations = []
        for root, _, files in os.walk(CASE_STUDIES_DIR):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()

                    mermaid_blocks = re.findall(r"```mermaid\n(.*?)\n```", content, re.DOTALL)
                    for block_idx, block in enumerate(mermaid_blocks):
                        for line_idx, line in enumerate(block.splitlines(), 1):
                            labels = re.findall(r"\|([^\|]+)\|", line)
                            for label in labels:
                                if label.startswith('"') and label.endswith('"'):
                                    continue
                                if any(ch in label for ch in "[]()"):
                                    violations.append(
                                        f"{rel_path} (block {block_idx}, line {line_idx}): |{label}|"
                                    )

        self.assertEqual(
            violations,
            [],
            f"Found unquoted brackets/parens in Mermaid edge labels (causes browser syntax error):\n"
            + "\n".join(violations),
        )

    def test_no_raw_tags_or_broken_syntax_in_mermaid(self):
        """Mermaid blocks must not contain unescaped HTML tags (e.g. <think>) that break SVG rendering."""
        violations = []
        tag_pattern = re.compile(r"<\s*/?\s*(?:think|tool_call)[^>]*>")

        for root, _, files in os.walk(CASE_STUDIES_DIR):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()

                    mermaid_blocks = re.findall(r"```mermaid\n(.*?)\n```", content, re.DOTALL)
                    for block_idx, block in enumerate(mermaid_blocks):
                        for line_idx, line in enumerate(block.splitlines(), 1):
                            if tag_pattern.search(line):
                                violations.append(
                                    f"{rel_path} (block {block_idx}, line {line_idx}): {line.strip()}"
                                )

        self.assertEqual(
            violations,
            [],
            f"Found raw <think> or <tool_call> tags inside Mermaid diagrams (breaks browser SVG XML):\n"
            + "\n".join(violations),
        )

    def test_no_encoding_replacement_characters(self):
        """Markdown files must not contain Unicode replacement character U+FFFD indicating corrupt encoding."""
        violations = []
        for root, _, files in os.walk(CASE_STUDIES_DIR):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            if "\ufffd" in line:
                                violations.append(f"{rel_path}:{line_num}: {line.strip()}")

        self.assertEqual(
            violations,
            [],
            f"Found corrupt Unicode replacement characters (\\ufffd) in markdown files:\n" + "\n".join(violations),
        )


# ============================================================================
# 5. Documentation Preparation Script & Config
# ============================================================================

class TestDocsPreparation(unittest.TestCase):
    """Validates docs preparation scripts and configuration."""

    def test_mathjax_config_instant_navigation(self):
        """MathJax helper must contain document$.subscribe for Material instant navigation."""
        mathjax_path = os.path.join(DOCS_DIR, "javascripts", "mathjax.js")
        if not os.path.exists(mathjax_path):
            from scripts.build_docs import prepare_docs
            prepare_docs()

        self.assertTrue(os.path.exists(mathjax_path), "docs/javascripts/mathjax.js must exist")
        with open(mathjax_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("document$.subscribe", content)
        self.assertIn("MathJax.typesetPromise", content)
        self.assertIn("arithmatex", content)


# ============================================================================
# 6. Static Site HTML Build Integrity
# ============================================================================

class TestBuiltSiteIntegrity(unittest.TestCase):
    """Validates the generated static site HTML for correct math rendering and zero visual glitches."""

    @classmethod
    def setUpClass(cls):
        site_case_15 = os.path.join(SITE_DIR, "case-studies", "15-deterministic-event-sourced-replay", "index.html")
        if not os.path.exists(site_case_15):
            from scripts.build_docs import prepare_docs, run_mkdocs_build
            prepare_docs()
            run_mkdocs_build()

    def test_all_case_studies_generated(self):
        """Every case study directory must have a built index.html."""
        all_dirs = get_all_case_study_dirs()
        for d in all_dirs:
            matches = [item for item in os.listdir(os.path.join(SITE_DIR, "case-studies")) if item == d]
            self.assertTrue(len(matches) > 0, f"Case study directory {d} not found in site/")
            html_file = os.path.join(SITE_DIR, "case-studies", matches[0], "index.html")
            self.assertTrue(os.path.exists(html_file), f"Missing index.html for {matches[0]}")

    def test_no_dangling_literal_dollars_around_arithmatex(self):
        """Built HTML must not contain dangling literal $ around arithmatex spans/divs."""
        dangling_pattern = re.compile(
            r"(\$\s*<(?:span|div) class=\"arithmatex\">|<(?:span|div) class=\"arithmatex\">[^<]*</(?:span|div)>\s*\$)"
        )
        violations = []

        for root, _, files in os.walk(SITE_DIR):
            for file in files:
                if file.endswith(".html"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    matches = dangling_pattern.findall(content)
                    if matches:
                        violations.append(f"{rel_path}: {matches[:3]}")

        self.assertEqual(
            violations,
            [],
            f"Found dangling dollar signs around arithmatex elements in built HTML:\n" + "\n".join(violations),
        )

    def test_no_misplaced_ampersand_in_arithmatex(self):
        """Built HTML must not have &gt; or &lt; inside math elements that cause MathJax parse errors."""
        bad_entity_pattern = re.compile(r"<(?:span|div) class=\"arithmatex\">[^<]*?&(?:gt|lt);[^<]*?</(?:span|div)>")
        violations = []

        for root, _, files in os.walk(SITE_DIR):
            for file in files:
                if file.endswith(".html"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    matches = bad_entity_pattern.findall(content)
                    if matches:
                        violations.append(f"{rel_path}: {matches[:2]}")

        self.assertEqual(
            violations,
            [],
            f"Found HTML entity (&gt;/&lt;) inside math blocks causing MathJax failures:\n" + "\n".join(violations),
        )

    def test_case_studies_mermaid_containers_rendered(self):
        """All case studies with mermaid blocks must contain rendered mermaid containers."""
        all_dirs = get_all_case_study_dirs()
        for d in all_dirs:
            md_path = os.path.join(CASE_STUDIES_DIR, d, "README.md")
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            if "```mermaid" not in md_content:
                continue

            html_path = os.path.join(SITE_DIR, "case-studies", d, "index.html")
            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            self.assertIn('class="mermaid"', html, f"{d} HTML missing mermaid containers")

    def test_no_unrendered_latex_macros_in_html(self):
        """Built HTML must not contain unrendered LaTeX macro strings like \\xrightleftharpoons."""
        bad_macros = ["\\xrightleftharpoons"]
        violations = []
        for root, _, files in os.walk(SITE_DIR):
            for file in files:
                if file.endswith(".html"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    for m in bad_macros:
                        if m in content:
                            violations.append(f"{rel_path}: {m}")
        self.assertEqual(
            violations,
            [],
            f"Found unrendered LaTeX macros in built HTML (MathJax parser failure):\n" + "\n".join(violations),
        )


    def test_mermaid_diagram_syntax_integrity(self):
        """All mermaid blocks must adhere to Mermaid 11.x syntax rules (no raw semicolons, unquoted special chars)."""
        all_dirs = get_all_case_study_dirs()
        syntax_errors = []

        for d in all_dirs:
            readme_path = os.path.join(CASE_STUDIES_DIR, d, "README.md")
            with open(readme_path, "r", encoding="utf-8") as f:
                content = f.read()

            blocks = re.findall(r"```mermaid\r?\n(.*?)```", content, re.DOTALL)
            for b_idx, block in enumerate(blocks, 1):
                lines = block.strip().split("\n")
                if not lines:
                    continue
                dtype = lines[0].strip()

                for line_no, raw_line in enumerate(lines, 1):
                    line = raw_line.strip()
                    if not line or line.startswith("%%"):
                        continue

                    # Sequence diagram checks
                    if dtype.startswith("sequenceDiagram"):
                        # Semicolons in sequence diagrams are statement terminators
                        if ";" in line and not line.startswith("%%"):
                            syntax_errors.append(f"{d} (block #{b_idx}, line {line_no}): Unquoted semicolon in sequence diagram: '{line}'")

                        # Participant / actor alias checks (must quote if parens or slashes present)
                        if line.startswith(("participant ", "actor ")) and " as " in line:
                            alias = line.split(" as ", 1)[1].strip()
                            if any(c in alias for c in "()[]{}&;/") and not (alias.startswith('"') and alias.endswith('"')):
                                syntax_errors.append(f"{d} (block #{b_idx}, line {line_no}): Unquoted special characters in participant alias: '{line}'")

                        # Message checks (after colon)
                        if ":" in line and not line.startswith(("participant", "actor", "note", "Note", "autonumber", "box", "end", "rect", "loop", "alt", "else", "par", "and", "critical", "option", "break")):
                            msg = line.split(":", 1)[1].strip()
                            # Unquoted -> in message
                            if "->" in msg and not (msg.startswith('"') and msg.endswith('"')):
                                syntax_errors.append(f"{d} (block #{b_idx}, line {line_no}): Unquoted '->' inside sequence message: '{line}'")
                            # Unescaped HTML brackets like <commit-hash>
                            if re.search(r"<[a-zA-Z0-9_\-]+>", msg):
                                syntax_errors.append(f"{d} (block #{b_idx}, line {line_no}): Unescaped HTML tag in sequence message: '{line}'")

                    # Quadrant chart checks
                    if dtype.startswith("quadrantChart"):
                        if line.startswith(("x-axis", "y-axis")):
                            if "(" in line or ")" in line or "/" in line:
                                syntax_errors.append(f"{d} (block #{b_idx}, line {line_no}): Parentheses or slashes in quadrantChart axis label: '{line}'")

        self.assertEqual(
            syntax_errors,
            [],
            "Found Mermaid syntax errors that fail under Mermaid 11.x:\n" + "\n".join(syntax_errors),
        )


if __name__ == "__main__":
    unittest.main()

