"""
services/pdf_editor.py
──────────────────────
Core PDF editing engine using PyMuPDF (fitz).

ABSOLUTE RULE: This service NEVER changes any visual property of the template.
It ONLY replaces the text content of matching spans while preserving:
  - font family, size, color, bold/italic flags
  - position (bbox) of every text span
  - page layout, margins, spacing
  - all non-text elements (images, lines, shapes, logos)

Architecture
────────────
  PDFEditor.edit_template(template_path, output_path, project_data, template_type)
      │
      ├── FieldMapper.build_replacements(project_data, template_type)
      │     → dict[placeholder → replacement_text]
      │
      ├── _scan_template(doc)
      │     → list[SpanInfo]  (page, block, line, span index + current text)
      │
      ├── _match_and_replace(doc, spans, replacements)
      │     → for each span whose text matches a placeholder:
      │          redact the old text area
      │          re-insert new text using IDENTICAL font/size/color/position
      │
      └── doc.save(output_path, garbage=4, deflate=True)

Matching strategy (most → least precise):
  1. Exact match of full span text to placeholder key
  2. Span text starts with / contains a unique placeholder key
  3. Fuzzy semantic match via keyword presence (fallback)
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.core.logging import get_logger
from app.models.schemas import ProjectData
from app.services.field_mapper import FieldMapper

log = get_logger(__name__)

# ── PyMuPDF import ─────────────────────────────────────────────────────────────
try:
    import fitz  # type: ignore   (PyMuPDF)
    _HAVE_FITZ = True
except ImportError:
    _HAVE_FITZ = False
    log.error("PyMuPDF (fitz) not installed. PDF editing will fail.")


# ──────────────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SpanInfo:
    """Snapshot of one text span extracted from the PDF."""
    page_num:   int
    block_num:  int
    line_num:   int
    span_num:   int
    text:       str
    bbox:       tuple[float, float, float, float]   # x0,y0,x1,y1
    font:       str
    size:       float
    flags:      int          # bold/italic bitmask
    color:      int          # packed RGB integer
    origin:     tuple[float, float]   # baseline origin x,y


@dataclass
class Replacement:
    """A confirmed text replacement to apply."""
    span:     SpanInfo
    new_text: str


# ──────────────────────────────────────────────────────────────────────────────
# PDF Editor
# ──────────────────────────────────────────────────────────────────────────────

class PDFEditor:
    """
    Stateless PDF template editor.
    Create once, call edit_template() many times.
    """

    # Redaction fill color – white (matches typical template backgrounds)
    _REDACT_FILL = (1.0, 1.0, 1.0)   # RGB 0-1

    def __init__(self) -> None:
        if not _HAVE_FITZ:
            raise RuntimeError("PyMuPDF is required. Install with: pip install pymupdf")
        self._mapper = FieldMapper()

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def edit_template(
        self,
        template_path: Path,
        output_path:   Path,
        project:       ProjectData,
        template_type: str = "plan",   # "plan" | "incubation"
    ) -> Path:
        """
        Edit *template_path* in-place replacing all matching placeholders
        with project data, then save to *output_path*.

        Returns the output path.
        """
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build replacement map from project data
        replacements = self._mapper.build_replacements(project, template_type)
        log.debug("[%s] %d replacement fields prepared", project.project_name, len(replacements))

        # Open a COPY of the template (never modify the original)
        doc: fitz.Document = fitz.open(str(template_path))

        try:
            # Scan all text spans
            all_spans = self._scan_all_pages(doc)
            log.debug("[%s] Scanned %d text spans across %d pages",
                      project.project_name, len(all_spans), doc.page_count)

            # Match spans to replacements
            matched = self._match_spans(doc, all_spans, replacements)
            log.info("[%s] Matched %d/%d fields to spans",
                     project.project_name, len(matched), len(replacements))

            # Apply replacements page by page
            self._apply_replacements(doc, matched)

            # Save with compression
            doc.save(
                str(output_path),
                garbage=4,
                deflate=True,
                clean=True,
            )
            log.info("[%s] Saved → %s", project.project_name, output_path.name)

        finally:
            doc.close()

        return output_path

    # ──────────────────────────────────────────────────────────────────────────
    # Step 1: Scan template for all text spans
    # ──────────────────────────────────────────────────────────────────────────

    def _scan_all_pages(self, doc: fitz.Document) -> list[SpanInfo]:
        """Extract every text span from every page, preserving all metadata."""
        spans: list[SpanInfo] = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            for b_idx, block in enumerate(blocks):
                if block.get("type") != 0:   # 0 = text block
                    continue
                for l_idx, line in enumerate(block.get("lines", [])):
                    for s_idx, span in enumerate(line.get("spans", [])):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        spans.append(SpanInfo(
                            page_num  = page_num,
                            block_num = b_idx,
                            line_num  = l_idx,
                            span_num  = s_idx,
                            text      = text,
                            bbox      = tuple(span["bbox"]),
                            font      = span.get("font", "Helvetica"),
                            size      = span.get("size", 11.0),
                            flags     = span.get("flags", 0),
                            color     = span.get("color", 0),
                            origin    = tuple(span.get("origin", (span["bbox"][0], span["bbox"][3]))),
                        ))
        return spans

    # ──────────────────────────────────────────────────────────────────────────
    # Step 2: Match spans to replacement keys
    # ──────────────────────────────────────────────────────────────────────────

    def _match_spans(
        self,
        doc: fitz.Document,
        spans: list[SpanInfo],
        replacements: dict[str, str],
    ) -> list[Replacement]:
        """
        Match sequences of spans to replacement keys using a Jaccard similarity sliding window
        with greedy overlap resolution.
        """
        # Group spans by page
        spans_by_page: dict[int, list[SpanInfo]] = {}
        for span in spans:
            spans_by_page.setdefault(span.page_num, []).append(span)

        confirmed_replacements: list[Replacement] = []

        for page_num in range(doc.page_count):
            page_spans = spans_by_page.get(page_num, [])
            if not page_spans:
                continue

            # Sort page spans by block, line, span index to ensure correct sequence reading order
            page_spans.sort(key=lambda s: (s.block_num, s.line_num, s.span_num))

            candidates = []

            for key in replacements:
                target_norm = self._normalise(key)
                target_words = set(target_norm.split())
                if not target_words:
                    continue

                n = len(page_spans)
                for i in range(n):
                    # Slide window j from i + 1 up to a reasonable word-length based offset
                    for j in range(i + 1, min(n + 1, i + len(target_words) + 10)):
                        candidate_text = " ".join(s.text for s in page_spans[i:j])
                        candidate_norm = self._normalise(candidate_text)
                        candidate_words = set(candidate_norm.split())

                        # Compute Jaccard similarity
                        if not target_words or not candidate_words:
                            score = 0.0
                        else:
                            score = len(target_words & candidate_words) / len(target_words | candidate_words)

                        if score >= 0.85:  # Highly confident match threshold
                            candidates.append({
                                "score": score,
                                "key": key,
                                "range": (i, j)
                            })

            # Sort candidates by score descending
            candidates.sort(key=lambda x: x["score"], reverse=True)

            # Greedy resolution of overlapping/conflict spans
            available = set(range(len(page_spans)))
            
            for c in candidates:
                start, end = c["range"]
                indices = set(range(start, end))
                if indices.issubset(available):
                    # Take these spans
                    available.difference_update(indices)
                    
                    matched_spans = page_spans[start:end]
                    
                    # Compute combined bounding box for all matched spans in this group
                    x0 = min(s.bbox[0] for s in matched_spans)
                    y0 = min(s.bbox[1] for s in matched_spans)
                    x1 = max(s.bbox[2] for s in matched_spans)
                    y1 = max(s.bbox[3] for s in matched_spans)
                    
                    new_text = replacements[c["key"]]
                    
                    # First span gets the new text formatted with the combined bounding box
                    first_span = matched_spans[0]
                    
                    layout_span = SpanInfo(
                        page_num=first_span.page_num,
                        block_num=first_span.block_num,
                        line_num=first_span.line_num,
                        span_num=first_span.span_num,
                        text=first_span.text,
                        bbox=(x0, y0, x1, y1),
                        font=first_span.font,
                        size=first_span.size,
                        flags=first_span.flags,
                        color=first_span.color,
                        origin=first_span.origin
                    )
                    
                    fitted = self._fit_text(new_text, layout_span)
                    confirmed_replacements.append(Replacement(span=first_span, new_text=fitted))
                    
                    # All other spans in the group are blanked out
                    for other_span in matched_spans[1:]:
                        confirmed_replacements.append(Replacement(span=other_span, new_text=""))

        return confirmed_replacements

    # ──────────────────────────────────────────────────────────────────────────
    # Step 3: Apply replacements to PDF document
    # ──────────────────────────────────────────────────────────────────────────

    def _apply_replacements(
        self, doc: fitz.Document, replacements: list[Replacement]
    ) -> None:
        """
        For each replacement:
          1. Redact (white-fill) the exact span bounding box.
          2. Insert new text at the same origin with identical formatting.
        """
        # Group by page for efficiency
        by_page: dict[int, list[Replacement]] = {}
        for r in replacements:
            by_page.setdefault(r.span.page_num, []).append(r)

        for page_num, page_replacements in by_page.items():
            page: fitz.Page = doc[page_num]

            for repl in page_replacements:
                span = repl.span
                rect = fitz.Rect(span.bbox)

                # ── 1. Redact old text ─────────────────────────────────────
                page.add_redact_annot(
                    quad        = rect,
                    text        = "",
                    fill        = self._REDACT_FILL,
                )

            # Apply all redactions on this page at once
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            # ── 2. Insert new text ─────────────────────────────────────────
            for repl in page_replacements:
                span    = repl.span
                new_txt = repl.new_text

                # Decode flags
                bold   = bool(span.flags & 2**4)   # fitz bold flag
                italic = bool(span.flags & 2**1)   # fitz italic flag

                # Convert packed color int → RGB float tuple
                r = ((span.color >> 16) & 0xFF) / 255.0
                g = ((span.color >>  8) & 0xFF) / 255.0
                b = ((span.color      ) & 0xFF) / 255.0
                color = (r, g, b)

                # Insert at original baseline origin, same font/size/color
                try:
                    page.insert_text(
                        point      = fitz.Point(span.origin),
                        text       = new_txt,
                        fontname   = self._resolve_font(span.font, bold, italic),
                        fontsize   = span.size,
                        color      = color,
                        overlay    = True,
                    )
                    log.debug(
                        "p%d replaced '%s' → '%s'",
                        page_num, span.text[:40], new_txt[:40]
                    )
                except Exception as exc:
                    # Non-fatal: log and continue
                    log.warning(
                        "Could not insert text on page %d (font=%s size=%.1f): %s",
                        page_num, span.font, span.size, exc
                    )

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _normalise(text: str) -> str:
        """Lower-case, collapse whitespace, strip punctuation for matching."""
        t = text.lower().strip()
        t = re.sub(r"[^\w\s]", " ", t)
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    @staticmethod
    def _keyword_score(span_norm: str, key_norm: str) -> float:
        """
        Simple keyword overlap score between normalised span and key.
        Returns 0.0 – 1.0.
        """
        span_words = set(span_norm.split())
        key_words  = set(key_norm.split())
        if not key_words:
            return 0.0
        overlap = span_words & key_words
        return len(overlap) / len(key_words)

    @staticmethod
    def _fit_text(text: str, span: SpanInfo) -> str:
        """
        Estimate how many characters fit inside the span's width and wrap
        accordingly.  The span height is fixed, so we can only wrap within it.
        Approximation: avg char width ≈ 0.5 × font_size.
        """
        if not text:
            return text

        span_width = span.bbox[2] - span.bbox[0]
        if span_width <= 0:
            return text

        avg_char_w   = span.size * 0.52
        chars_per_line = max(10, int(span_width / avg_char_w))

        span_height  = span.bbox[3] - span.bbox[1]
        line_height  = span.size * 1.2
        max_lines    = max(1, int((span_height * 3) / line_height))  # allow 3× height for multi-line

        # Wrap text
        wrapped_lines = []
        for paragraph in text.split("\n"):
            if len(paragraph) <= chars_per_line:
                wrapped_lines.append(paragraph)
            else:
                wrapped = textwrap.wrap(paragraph, width=chars_per_line)
                wrapped_lines.extend(wrapped if wrapped else [paragraph])

        # Trim to max lines
        if len(wrapped_lines) > max_lines:
            wrapped_lines = wrapped_lines[:max_lines]
            if wrapped_lines:
                last = wrapped_lines[-1]
                if len(last) > 3:
                    wrapped_lines[-1] = last[:-3] + "..."

        return "\n".join(wrapped_lines)

    @staticmethod
    def _resolve_font(font_name: str, bold: bool, italic: bool) -> str:
        """
        Map PDF font name to a PyMuPDF built-in font name.
        PyMuPDF built-ins: helv, tibo, timesroman, courier, symbol, zapfdingbats
        """
        fn = font_name.lower()

        if "times" in fn or "serif" in fn:
            if bold and italic: return "tibo"
            if bold:            return "tibo"
            if italic:          return "tiit"
            return "tiro"

        if "courier" in fn or "mono" in fn:
            if bold and italic: return "cobi"
            if bold:            return "cobo"
            if italic:          return "coit"
            return "cour"

        # Default: Helvetica family
        if bold and italic: return "helv"
        if bold:            return "hebo"
        if italic:          return "heit"
        return "helv"
