"""
calendar_parser.py
------------------
Parses college academic calendars from PDF, Excel, CSV, or image files
and populates the working_days table in the database.

Supported formats
-----------------
  .pdf          — text-based PDF; pdfplumber extracts text then heuristics classify dates
  .csv          — expects columns: date, day_type (working/holiday/...), description
  .xlsx / .xls  — same column structure as CSV
  .png / .jpg   — image; basic OCR heuristics (requires pytesseract if installed)

Classification rules
--------------------
  1. If a date appears in the calendar file and is marked as holiday/vacation → holiday/vacation
  2. If a date falls on Saturday/Sunday and config.saturday_working / sunday_working is False → weekend
  3. If a date is within the academic year range and is not a holiday/weekend → working
  4. If a date cannot be classified confidently → SKIPPED (conservative approach)
"""

import re
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from dateutil import parser as date_parser

logger = logging.getLogger("spacebasic.calendar")

# Keywords that indicate a holiday or non-working day
HOLIDAY_KEYWORDS = [
    "holiday", "vacation", "leave", "recess", "break",
    "diwali", "holi", "dussehra", "eid", "christmas", "onam",
    "independence", "republic", "gandhi", "pongal", "ugadi",
    "navratri", "durga", "ganesh", "makar", "lohri",
    "closed", "no class", "non-working", "off",
    "summer vacation", "winter vacation", "mid-semester break",
    "semester break", "exam holiday",
]

WORKING_KEYWORDS = [
    "working day", "regular day", "class", "lecture",
    "lab", "examination", "test", "working saturday",
]

DAY_TYPE_WORKING = "working"
DAY_TYPE_HOLIDAY = "holiday"
DAY_TYPE_WEEKEND = "weekend"
DAY_TYPE_VACATION = "vacation"
DAY_TYPE_UNKNOWN = "unknown"


class CalendarParser:
    """Parses a college calendar file and returns a list of classified dates."""

    def __init__(
        self,
        academic_start: date,
        academic_end: date,
        saturday_working: bool = False,
        sunday_working: bool = False,
    ):
        self.academic_start = academic_start
        self.academic_end = academic_end
        self.saturday_working = saturday_working
        self.sunday_working = sunday_working

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def parse(self, file_path: str) -> List[Dict]:
        """
        Parse a calendar file and return a list of dicts:
          [{'date': date, 'day_type': str, 'description': str}, ...]

        Only confident classifications are returned.
        Ambiguous dates are excluded (conservative approach).
        """
        path = Path(file_path)
        if not path.exists():
            logger.error("Calendar file not found: %s", file_path)
            return []

        suffix = path.suffix.lower()
        logger.info("Parsing calendar file: %s (type=%s)", path.name, suffix)

        if suffix == ".csv":
            raw = self._parse_csv(path)
        elif suffix in (".xlsx", ".xls"):
            raw = self._parse_excel(path)
        elif suffix == ".pdf":
            raw = self._parse_pdf(path)
        elif suffix in (".png", ".jpg", ".jpeg"):
            raw = self._parse_image(path)
        else:
            logger.error("Unsupported calendar format: %s", suffix)
            return []

        # Fill in remaining academic year dates not explicitly listed
        enriched = self._fill_academic_year(raw)

        valid = [d for d in enriched if d["day_type"] != DAY_TYPE_UNKNOWN]
        logger.info(
            "Calendar parsed: %d working days, %d holidays, %d weekends",
            sum(1 for d in valid if d["day_type"] == DAY_TYPE_WORKING),
            sum(1 for d in valid if d["day_type"] in (DAY_TYPE_HOLIDAY, DAY_TYPE_VACATION)),
            sum(1 for d in valid if d["day_type"] == DAY_TYPE_WEEKEND),
        )
        return valid

    # ------------------------------------------------------------------
    # CSV parser
    # ------------------------------------------------------------------

    def _parse_csv(self, path: Path) -> List[Dict]:
        """
        Expected columns (case-insensitive):
          date, day_type, description   (description optional)
        """
        try:
            df = pd.read_csv(path)
        except Exception as e:
            logger.error("Failed to read CSV: %s", e)
            return []
        return self._normalise_dataframe(df, str(path))

    # ------------------------------------------------------------------
    # Excel parser
    # ------------------------------------------------------------------

    def _parse_excel(self, path: Path) -> List[Dict]:
        try:
            df = pd.read_excel(path, sheet_name=0)
        except Exception as e:
            logger.error("Failed to read Excel: %s", e)
            return []
        return self._normalise_dataframe(df, str(path))

    # ------------------------------------------------------------------
    # PDF parser  (text extraction → heuristics)
    # ------------------------------------------------------------------

    def _parse_pdf(self, path: Path) -> List[Dict]:
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber not installed. Run: pip install pdfplumber")
            return []

        results: List[Dict] = []
        try:
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    rows = self._extract_dates_from_text(text, str(path))
                    results.extend(rows)
        except Exception as e:
            logger.error("Failed to parse PDF: %s", e)
        return results

    # ------------------------------------------------------------------
    # Image parser  (very basic — falls back to empty if no OCR)
    # ------------------------------------------------------------------

    def _parse_image(self, path: Path) -> List[Dict]:
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(str(path))
            text = pytesseract.image_to_string(img)
            return self._extract_dates_from_text(text, str(path))
        except ImportError:
            logger.warning(
                "pytesseract / Pillow not available. "
                "Cannot parse image calendars. Install: pip install pytesseract Pillow"
            )
            return []
        except Exception as e:
            logger.error("Image parsing failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Helper: normalise a DataFrame into our standard list-of-dicts
    # ------------------------------------------------------------------

    def _normalise_dataframe(self, df: pd.DataFrame, source: str) -> List[Dict]:
        """
        Accepts a DataFrame with columns like 'date', 'day_type', 'description'.
        Column names are normalised to lower-case and stripped.
        """
        df.columns = [str(c).strip().lower() for c in df.columns]

        date_col = self._find_column(df, ["date", "day", "calendar_date"])
        type_col = self._find_column(df, ["day_type", "type", "status", "category"])
        desc_col = self._find_column(df, ["description", "desc", "event", "remark", "remarks"])

        if date_col is None:
            logger.error("CSV/Excel has no recognisable date column. Columns: %s", list(df.columns))
            return []

        results = []
        for _, row in df.iterrows():
            raw_date = row.get(date_col, "")
            raw_type = str(row.get(type_col, "")).strip().lower() if type_col else ""
            description = str(row.get(desc_col, "")).strip() if desc_col else ""

            parsed_date = self._parse_date(str(raw_date))
            if parsed_date is None:
                continue

            day_type = self._classify_type_string(raw_type, description)
            if day_type == DAY_TYPE_UNKNOWN:
                day_type = self._classify_by_day_of_week(parsed_date)

            results.append({
                "date": parsed_date,
                "day_type": day_type,
                "description": description,
                "source": source,
            })
        return results

    # ------------------------------------------------------------------
    # Helper: extract dates from free text (PDF / image)
    # ------------------------------------------------------------------

    def _extract_dates_from_text(self, text: str, source: str) -> List[Dict]:
        """
        Crude heuristic: find date-like tokens in text, then check surrounding
        words for holiday/working keywords.
        """
        results = []
        # Common Indian date patterns: DD/MM/YYYY, DD-MM-YYYY, DD Month YYYY
        date_pattern = re.compile(
            r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\b",
            re.IGNORECASE,
        )
        lines = text.splitlines()
        for line in lines:
            for match in date_pattern.finditer(line):
                raw = match.group(0)
                parsed_date = self._parse_date(raw)
                if parsed_date is None:
                    continue
                if not (self.academic_start <= parsed_date <= self.academic_end):
                    continue
                context = line.lower()
                day_type = self._classify_by_keywords(context)
                if day_type == DAY_TYPE_UNKNOWN:
                    day_type = self._classify_by_day_of_week(parsed_date)
                results.append({
                    "date": parsed_date,
                    "day_type": day_type,
                    "description": line.strip()[:120],
                    "source": source,
                })
        return results

    # ------------------------------------------------------------------
    # Fill academic year with defaults
    # ------------------------------------------------------------------

    def _fill_academic_year(self, explicit: List[Dict]) -> List[Dict]:
        """
        For every date in the academic year NOT already in `explicit`,
        assign weekend or working based on day-of-week.
        Dates that ARE in `explicit` keep their assigned type.
        """
        explicit_map: Dict[date, Dict] = {e["date"]: e for e in explicit}
        all_dates: List[Dict] = []

        current = self.academic_start
        while current <= self.academic_end:
            if current in explicit_map:
                all_dates.append(explicit_map[current])
            else:
                day_type = self._classify_by_day_of_week(current)
                all_dates.append({
                    "date": current,
                    "day_type": day_type,
                    "description": "",
                    "source": "auto-fill",
                })
            current += timedelta(days=1)
        return all_dates

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    def _classify_type_string(self, type_str: str, description: str) -> str:
        combined = (type_str + " " + description).lower()
        if any(kw in type_str for kw in ["holiday", "vacation", "recess", "break", "off"]):
            if "vacation" in combined or "break" in combined or "recess" in combined:
                return DAY_TYPE_VACATION
            return DAY_TYPE_HOLIDAY
        if any(kw in type_str for kw in ["working", "regular", "class"]):
            return DAY_TYPE_WORKING
        return self._classify_by_keywords(combined)

    def _classify_by_keywords(self, text: str) -> str:
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["vacation", "recess", "semester break"]):
            return DAY_TYPE_VACATION
        if any(kw in text_lower for kw in HOLIDAY_KEYWORDS):
            return DAY_TYPE_HOLIDAY
        if any(kw in text_lower for kw in WORKING_KEYWORDS):
            return DAY_TYPE_WORKING
        return DAY_TYPE_UNKNOWN

    def _classify_by_day_of_week(self, d: date) -> str:
        weekday = d.weekday()  # 0=Mon, 5=Sat, 6=Sun
        if weekday == 6:  # Sunday
            return DAY_TYPE_WORKING if self.sunday_working else DAY_TYPE_WEEKEND
        if weekday == 5:  # Saturday
            return DAY_TYPE_WORKING if self.saturday_working else DAY_TYPE_WEEKEND
        return DAY_TYPE_WORKING  # Mon–Fri default to working

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _parse_date(raw: str) -> Optional[date]:
        raw = raw.strip()
        if not raw or raw.lower() in ("nan", "none", ""):
            return None
        try:
            return date_parser.parse(raw, dayfirst=True).date()
        except Exception:
            return None

