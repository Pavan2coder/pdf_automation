"""
services/field_mapper.py
─────────────────────────
Maps ProjectData fields → template-specific text replacements.

Two template types are supported:
  • "plan"       – Multi-slide Plan PPT-style PDF template
  • "incubation" – MSME Incubation form PDF template

How it works
────────────
  1. _PLAN_MAP / _INCUBATION_MAP define:
       { "template_placeholder_text" : "project_data_field_name" }
     where template_placeholder_text is the EXACT text (or close match) that
     appears in the template PDF, and project_data_field_name is the attribute
     name on ProjectData.

  2. build_replacements() resolves each field name to its actual string value
     from the ProjectData instance and returns:
       { "template_placeholder_text" : "new content string" }

  3. PDFEditor consumes this dict to do the actual text replacement.

Extending
─────────
  To support a new template, add a new _XXX_MAP dict and a case in
  build_replacements().  No other changes needed.
"""

from __future__ import annotations

from typing import Any, Optional

from app.core.logging import get_logger
from app.models.schemas import ProjectData

log = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Field maps  { placeholder_text_in_pdf : project_data_attribute }
# ──────────────────────────────────────────────────────────────────────────────
# These keys are the ACTUAL text strings that appear in the uploaded template
# PDFs (the NoPhoneDrive plan and MSME Incubation form).
# The PDFEditor matches each span's text against these keys.

_PLAN_MAP: dict[str, str] = {
    # ── Slide / section title area ────────────────────────────────────────────
    "RESTRICT MOBILE USAGE WHILE DRIVING":      "project_title",
    '"NoPhoneDrive"':                           "project_name",
    "NoPhoneDrive":                             "project_name",

    # ── PROBLEM STATEMENT slide ───────────────────────────────────────────────
    "General driving conditions, changes in road environment and traffic conditions have a great\nimpact on driving control behavior":
                                                "problem_statement",
    "External distractions like mobile usage for calls, notifications, messages on phone will impact\ndriving which leads to road accidents":
                                                "problem_statement",

    # ── CUSTOMER SEGMENT slide ───────────────────────────────────────────────
    "The particular customer segment selected for the project aiming to restrict mobile usage while\ndriving would typically be drivers who frequently use their mobile devices while on the road.":
                                                "customer_segment",
    "Individual Drivers":                       "customer_segment",

    # ── CUSTOMER SURVEY slide ────────────────────────────────────────────────
    "Which activities do you typically engage in on your mobile phone while driving?":
                                                "customer_survey",
    "Number of customers surveyed:10 (ongoing)":"customer_survey",

    # ── MARKET SURVEY slide ──────────────────────────────────────────────────
    "The global automotive motors market in terms of revenue was \nestimated to be worth $23.0 billion in 2022 and is expected to reach \n$28.7 billion by 2027":
                                                "market_analysis",
    "Growing at a CAGR of 4.5% from 2022 to 2027":
                                                "market_analysis",
    "India with the third largest road network in the world, the total\nnumber of vehicles in fiscal year 2022 stood at 326.3 million":
                                                "market_analysis",
    "India growing at a CAGR of over 9% between 2022-27.":
                                                "market_analysis",

    # ── POTENTIAL SOLUTIONS slide ────────────────────────────────────────────
    'We are creating an app "NoPhoneDrive" which restricts mobile usage while driving.':
                                                "idea_description",
    "Technology solution identified:Motion Sensor Technology,SmartPhone Integration with\nVehicle":
                                                "technology_stack",

    # ── UNIQUENESS slide ─────────────────────────────────────────────────────
    "Detecting when the user is driving through GPS or other sensors":
                                                "uniqueness",
    "Blocking incoming calls and notifications": "uniqueness",
    "Disabling certain app functionalities":     "features",
    "Providing customizable settings to promote safe driving habits":
                                                "features",

    # ── PROTOTYPE COST table ─────────────────────────────────────────────────
    "7,41,000":                                 "cost_estimation",
    "Total Estimated Cost":                     "cost_estimation",

    # ── COMPETITOR ANALYSIS slide ────────────────────────────────────────────
    "CellControl:CellControl is an anti-distraction app that disables your\nphone, so you can entirely focus on the road":
                                                "competitor_analysis",
    "Our application behaves according to speed of the vehicle and \nrestricts the calls and messages and sends auto-reply to the person \nwho is trying to reach the user":
                                                "uniqueness",

    # ── BUSINESS MODEL ───────────────────────────────────────────────────────
    "App Purchases":                            "revenue_streams",
    "enterprise Solution":                      "revenue_streams",

    # ── ROAD MAP ─────────────────────────────────────────────────────────────
    "Start- 18/05/2023":                        "roadmap",
    "PoC Development- (6 to 8 weeks)-September":"implementation_plan",
    "Solution Validation-(8weeks) -October":    "roadmap",

    # ── MENTORS ──────────────────────────────────────────────────────────────
    "Mr. SK. Gouse Pasha":                      "guide_name",
    "Assistant Professor":                      "guide_designation",
}


_INCUBATION_MAP: dict[str, str] = {
    # Row 1 – Name
    "KOLLURU SRI NITHYA":               "primary_team_member_name",
    # Row 2 – Email
    "21r21a66g3@mlrinstitutions.ac.in": "primary_team_member_email",
    # Row 3 – Mobile
    "7337332369":                       "primary_team_member_phone",
    # Row 4 – State
    "TELANGANA":                        "state",
    # Row 5 – District
    "SANGAREDDY":                       "district",
    # Row 6 – Idea Sector
    "Services, Education, Hospitality, Media, Publishing, Entertainment, Design, Wellness,\nLogistics, Sports and any related sub-sector":
                                        "theme",
    # Row 7 – Title
    "Restrict Mobile usage while driving NoPhoneDrive":
                                        "project_title",
    # Row 8 – Uniqueness
    "Detecting when the user is driving through GPS or other sensors ,Blocking incoming calls and\nnotifications,Disabling certain app functionalities,Providing customizable settings to promote\nsafe driving habits":
                                        "uniqueness",
    # Row 9 – Concept & Objective
    "To Discourage drivers from using their mobile devices by implementing features that limit or\ndisable certain functionalities while the vehicle is in motion.It may include features such as\nblocking incoming calls, messages, and notifications, as well as disabling social media and\ninternet access.":
                                        "objectives",
    "The ultimate goal is to encourage responsible and focused driving, reducing\nthe risk of accidents caused by mobile phone distractions.":
                                        "idea_description",
    # Row 10 – Application areas
    "In the transportation industry, it could promote safe driving practices among employees.":
                                        "applications",
    "Insurance companies could partner with the app to incentivize responsible mobile usage":
                                        "applications",
    # Row 11 – Market potential
    "As governments and organizations prioritize road safety, there is a substantial market\nopportunity for this app to be adopted widely, benefiting both individuals and society as a\nwhole.":
                                        "market_analysis",
}


# ──────────────────────────────────────────────────────────────────────────────
# Field Mapper
# ──────────────────────────────────────────────────────────────────────────────

class FieldMapper:
    """
    Converts a ProjectData instance into a flat dict of
    { template_placeholder_text → replacement_string }
    for a specific template type.
    """

    def build_replacements(
        self,
        project: ProjectData,
        template_type: str,
    ) -> dict[str, str]:
        """
        Parameters
        ----------
        project : ProjectData
            AI-extracted project information.
        template_type : "plan" | "incubation"

        Returns
        -------
        dict[str, str]
            Placeholder → replacement text ready for PDFEditor.
        """
        field_map = _PLAN_MAP if template_type == "plan" else _INCUBATION_MAP
        result: dict[str, str] = {}

        for placeholder, field_name in field_map.items():
            value = self._resolve(project, field_name)
            if value:
                result[placeholder] = value
            else:
                log.debug("No value for field '%s' – placeholder kept", field_name)

        log.debug(
            "[%s] %s template: %d/%d fields resolved",
            project.project_name, template_type,
            len(result), len(field_map),
        )
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Value resolution
    # ──────────────────────────────────────────────────────────────────────────

    def _resolve(self, project: ProjectData, field_name: str) -> Optional[str]:
        """
        Resolve a field name to a string value from the ProjectData.
        Handles special pseudo-fields like primary_team_member_*.
        """
        # ── Special: primary team member fields ──────────────────────────────
        if field_name.startswith("primary_team_member_"):
            attr = field_name.replace("primary_team_member_", "")
            return self._primary_member(project, attr)

        if field_name in ("state", "district"):
            return self._infer_location(project, field_name)

        # ── Standard ProjectData attribute ───────────────────────────────────
        value = getattr(project, field_name, None)

        if value is None:
            # Check extra_fields dict
            value = project.extra_fields.get(field_name)

        if value is None:
            return None

        # ── Serialise different types to string ───────────────────────────────
        if isinstance(value, str):
            return value.strip() or None

        if isinstance(value, list):
            # team_members list → formatted string
            if field_name == "team_members":
                return self._format_team(project)
            return "\n".join(str(v) for v in value) or None

        return str(value).strip() or None

    def _primary_member(self, project: ProjectData, attr: str) -> Optional[str]:
        """Get attribute from the first team member."""
        if not project.team_members:
            return None
        first = project.team_members[0]
        return getattr(first, attr, None)

    def _format_team(self, project: ProjectData) -> str:
        """Format team members as a readable list."""
        lines: list[str] = []
        for m in project.team_members:
            parts = [m.name]
            if m.roll_number:
                parts.append(m.roll_number)
            if m.phone:
                parts.append(m.phone)
            if m.email:
                parts.append(m.email)
            lines.append("  ".join(parts))
        return "\n".join(lines)

    def _infer_location(self, project: ProjectData, field: str) -> Optional[str]:
        """
        Infer state/district from institution name or team member details.
        Falls back to 'TELANGANA' / 'HYDERABAD' for MLR Institute projects.
        """
        inst = (project.institution or "").lower()
        if "mlr" in inst or "hyderabad" in inst or "telangana" in inst:
            return "TELANGANA" if field == "state" else "HYDERABAD"
        # Try to extract from guide department or other fields
        return None
