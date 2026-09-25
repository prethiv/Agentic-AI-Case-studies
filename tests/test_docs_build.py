"""
Unit tests for documentation preparation, math syntax, and built HTML integrity.
Ensures LaTeX equations, slashes, relational operators, and MathJax hooks render
properly in both GitHub Markdown and MkDocs Material static documentation.
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CASE_STUDIES_DIR = os.path.join(REPO_ROOT, "case-studies")
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
SITE_DIR = os.path.join(REPO_ROOT, "site")


class TestMarkdownMathSyntax(unittest.TestCase):
    """Validates markdown math formulas across all case studies for GitHub and MkDocs compatibility."""

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
        """Every display math block ($$) must have matching delimiters."""
        for root, _, files in os.walk(CASE_STUDIES_DIR):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Count isolated $$ lines (block math openers/closers)
                    isolated_count = len(re.findall(r"^\s*\$\$\s*$", content, re.MULTILINE))
                    self.assertEqual(
                        isolated_count % 2,
                        0,
                        f"Unpaired display math $$ delimiters in {rel_path} (count: {isolated_count})",
                    )

    def test_no_raw_relational_operators_in_math_mode(self):
        """Inline math with relational operators must use \\gt / \\lt to avoid HTML entity encoding (&gt;)."""
        violations = []
        raw_gt_pattern = re.compile(r"\$[^\$]*?\s+>\s+[^\$]*?\$")

        for root, _, files in os.walk(CASE_STUDIES_DIR):
            for file in files:
                if file.endswith(".md"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, REPO_ROOT)
                    with open(path, "r", encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            # Skip lines containing pure HTML or mermaid
                            if "flowchart" in line or "classDef" in line:
                                continue
                            if raw_gt_pattern.search(line):
                                violations.append(f"{rel_path}:{line_num}: {line.strip()}")

        self.assertEqual(
            violations,
            [],
            f"Found unescaped '>' in math mode (use \\gt to prevent HTML escaping):\n" + "\n".join(violations),
        )

    def test_case_study_11_equations_structure(self):
        """Case study 11 must contain required math blocks formatted on isolated lines."""
        readme_path = os.path.join(CASE_STUDIES_DIR, "11-hybrid-swarm-delegation-blackboard", "README.md")
        self.assertTrue(os.path.exists(readme_path), "Case study 11 README.md must exist")

        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check required formulas
        self.assertIn("\\text{BidScore}(A_i, T_j)", content)
        self.assertIn("\\mathcal{C}(A_i, T_j) = \\frac{1}{m}", content)
        self.assertIn("v \\not\\rightsquigarrow_{\\mathcal{G}} u", content)
        self.assertIn("\\text{Depth}(v) \\le D_{\\max}", content)
        self.assertIn("\\text{Depth}(v) \\gt D_{\\max}", content)
        self.assertIn("\\tau_k(t + 1) = \\max", content)

        # Check that display math blocks are preceded and followed by $$ on isolated lines
        block_pattern = re.compile(r"\n\$\$\n.*?\n\$\$\n", re.DOTALL)
        blocks = block_pattern.findall(content)
        self.assertGreaterEqual(len(blocks), 4, f"Expected at least 4 display math blocks in Case Study 11, found {len(blocks)}")


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


class TestBuiltSiteIntegrity(unittest.TestCase):
    """Validates the generated static site HTML for correct math rendering and zero visual glitches."""

    @classmethod
    def setUpClass(cls):
        # Ensure site is built before verifying HTML
        site_case_11 = os.path.join(SITE_DIR, "case-studies", "11-hybrid-swarm-delegation-blackboard", "index.html")
        if not os.path.exists(site_case_11):
            from scripts.build_docs import prepare_docs, run_mkdocs_build
            prepare_docs()
            run_mkdocs_build()

    def test_all_eleven_case_studies_generated(self):
        """Every case study (01 through 11) must have a built index.html."""
        for i in range(1, 12):
            prefix = f"{i:02d}-"
            matches = [d for d in os.listdir(os.path.join(SITE_DIR, "case-studies")) if d.startswith(prefix)]
            self.assertTrue(len(matches) > 0, f"Case study {prefix} directory not found in site/")
            html_file = os.path.join(SITE_DIR, "case-studies", matches[0], "index.html")
            self.assertTrue(os.path.exists(html_file), f"Missing index.html for {matches[0]}")

    def test_no_dangling_literal_dollars_around_arithmatex(self):
        """Built HTML must not contain dangling literal $ around arithmatex spans/divs."""
        dangling_pattern = re.compile(r"(\$\s*<(?:span|div) class=\"arithmatex\">|<(?:span|div) class=\"arithmatex\">[^<]*</(?:span|div)>\s*\$)")
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

    def test_case_study_11_html_renders_all_math_blocks(self):
        """Case study 11 built HTML must contain the correct arithmatex blocks."""
        html_path = os.path.join(SITE_DIR, "case-studies", "11-hybrid-swarm-delegation-blackboard", "index.html")
        self.assertTrue(os.path.exists(html_path))

        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Check for presence of arithmatex blocks (normalizing whitespace)
        norm_html = " ".join(html.split())
        self.assertIn('<div class="arithmatex">\\[ \\text{BidScore}(A_i, T_j)', norm_html)
        self.assertIn('<div class="arithmatex">\\[ \\mathcal{C}(A_i, T_j)', norm_html)
        self.assertIn('<div class="arithmatex">\\[ \\forall (u, v) \\in E: \\quad v \\not\\rightsquigarrow_{\\mathcal{G}} u \\]</div>', norm_html)
        self.assertIn('<div class="arithmatex">\\[ \\text{Depth}(v) \\le D_{\\max}, \\quad \\forall v \\in V \\]</div>', norm_html)
        self.assertIn('<span class="arithmatex">\\(\\text{Depth}(v) \\gt D_{\\max}\\)</span>', html)
        self.assertIn('<div class="arithmatex">\\[ \\tau_k(t + 1) = \\max', norm_html)


if __name__ == "__main__":
    unittest.main()
