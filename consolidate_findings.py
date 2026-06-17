import json
import os
from collections import defaultdict
from typing import List, Dict, Any

INTELLIGENCE_DIR = "output/intelligence"
CONSOLIDATED_PATH = "output/consolidated_findings.json"

SECTION_MAPPING = {
    "TOP DE ORIGEN DE ATAQUES": ["origin", "source", "attack_origin", "ip", "geo"],
    "TOP LOGIN": ["login", "authentication", "vpn", "access", "account"],
    "DIRECTORIO ACTIVO": ["active_directory", "ad", "account", "group", "domain"],
    "ACTIVIDAD DE USUARIOS ADMINISTRADORES": ["admin", "administrator", "privilege", "management"],
    "CAMBIOS EN EQUIPOS DE COMUNICACIONES": ["equipment", "communication", "device", "server"],
    "ACTIVIDADES SOSPECHOSAS – MALWARE - AMENAZAS": ["malware", "threat", "suspicious", "tor", "command"],
    "REPORTE DE VOLUMEN DE LOGS": ["volume", "log", "event", "count"],
}

def load_all_findings():
    """Load all findings from intelligence batches."""
    findings = []

    if not os.path.exists(INTELLIGENCE_DIR):
        return findings

    for file in sorted(os.listdir(INTELLIGENCE_DIR)):
        if not file.endswith(".json"):
            continue

        path = os.path.join(INTELLIGENCE_DIR, file)
        try:
            with open(path, "r", encoding="utf-8") as f:
                batch = json.load(f)
                batch_findings = batch.get("findings", [])
                findings.extend(batch_findings)
        except Exception as e:
            print(f"Error loading {file}: {e}")

    return findings

def deduplicate_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate findings by merging similar ones.
    Similar = same title or overlapping evidence.
    """
    deduplicated = {}

    for finding in findings:
        title = finding.get("title", "").lower().strip()

        if not title:
            continue

        # Use title as key (exact match deduplication)
        if title not in deduplicated:
            deduplicated[title] = finding
        else:
            # Merge evidence
            existing = deduplicated[title]
            existing_evidence = set(existing.get("key_evidence", []))
            new_evidence = set(finding.get("key_evidence", []))
            existing["key_evidence"] = list(existing_evidence | new_evidence)[:3]

            # Keep highest severity
            sev_map = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            existing_sev = sev_map.get(existing.get("severity", "low").lower(), 1)
            new_sev = sev_map.get(finding.get("severity", "low").lower(), 1)
            if new_sev > existing_sev:
                existing["severity"] = finding["severity"]

    return list(deduplicated.values())

def assign_primary_section(finding: Dict[str, Any]) -> str:
    """Assign a primary section to a finding based on its metadata."""

    # Check recommended_sections first
    recommended = finding.get("recommended_sections", [])
    if recommended:
        return recommended[0]

    # Fallback: infer from title and finding_type
    title = (finding.get("title", "") + " " + finding.get("finding_type", "")).lower()
    severity = finding.get("severity", "").lower()

    for section, keywords in SECTION_MAPPING.items():
        if any(kw in title for kw in keywords):
            return section

    # Default sections by severity
    if severity == "critical":
        return "REPORTE DE ALERTAS, INCIDENTES Y SUGERENCIAS"
    elif severity == "high":
        return "ACTIVIDADES SOSPECHOSAS – MALWARE - AMENAZAS"
    else:
        return "RESUMEN DE CASOS"

def consolidate():
    """
    Main consolidation pipeline:
    1. Load all findings
    2. Deduplicate
    3. Assign primary sections
    4. Output consolidated findings
    """

    print("Loading findings from intelligence batches...")
    findings = load_all_findings()
    print(f"  Found {len(findings)} raw findings")

    print("Deduplicating similar findings...")
    deduplicated = deduplicate_findings(findings)
    print(f"  Consolidated to {len(deduplicated)} unique findings")

    print("Assigning primary sections...")
    for finding in deduplicated:
        primary_section = assign_primary_section(finding)
        finding["primary_section"] = primary_section

    # Group by section for reference
    by_section = defaultdict(list)
    for finding in deduplicated:
        section = finding.get("primary_section", "RESUMEN DE CASOS")
        by_section[section].append(finding)

    print("\nFindings by section:")
    for section in [
        "PORTADA E INDICE",
        "RESUMEN EJECUTIVO",
        "INTRODUCCIÓN",
        "EQUIPOS MONITOREADOS A LA FECHA",
        "RESUMEN DE CASOS",
        "TOP DE ORIGEN DE ATAQUES",
        "ACTIVIDADES SOSPECHOSAS – MALWARE - AMENAZAS",
        "TOP LOGIN",
        "DIRECTORIO ACTIVO",
        "ACTIVIDAD DE USUARIOS ADMINISTRADORES",
        "CAMBIOS EN EQUIPOS DE COMUNICACIONES",
        "REPORTE DE ALERTAS, INCIDENTES Y SUGERENCIAS",
        "REPORTE DE VOLUMEN DE LOGS",
        "CONCLUSION"
    ]:
        count = len(by_section.get(section, []))
        if count > 0:
            print(f"  {section}: {count} findings")

    # Save consolidated findings
    os.makedirs("output", exist_ok=True)
    consolidated = {
        "total_findings": len(deduplicated),
        "findings": deduplicated,
        "by_section": {k: v for k, v in by_section.items() if v}
    }

    with open(CONSOLIDATED_PATH, "w", encoding="utf-8") as f:
        json.dump(consolidated, f, indent=2, ensure_ascii=False)

    print(f"\nConsolidated findings saved: {CONSOLIDATED_PATH}")
    return consolidated

if __name__ == "__main__":
    consolidate()
