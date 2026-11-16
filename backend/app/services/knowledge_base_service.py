from app.services.analytics_service import impact_for, severity_for_score

def entry_response(entry):
    return {"id": entry.id, "title": entry.title, "entry_type": entry.entry_type, "content": entry.content, "disaster_type": entry.disaster_type, "severity": entry.severity, "tags": [tag for tag in (entry.tags or "").split(",") if tag], "created_at": entry.created_at, "updated_at": entry.updated_at}

def matching_entries(report, entries, limit):
    severity = severity_for_score(impact_for(report)[0]); matches = []
    for entry in entries:
        reasons = []
        if entry.disaster_type:
            if entry.disaster_type.casefold() != report.disaster_type.casefold(): continue
            reasons.append("Matches disaster type")
        else: reasons.append("General disaster-response guidance")
        if entry.severity:
            if entry.severity != severity: continue
            reasons.append(f"Matches {severity.lower()} severity")
        if entry.tags: reasons.append("Tagged operational guidance")
        matches.append({"knowledge_entry": entry_response(entry), "match_reasons": reasons})
    return sorted(matches, key=lambda match: (-len(match["match_reasons"]), match["knowledge_entry"]["title"]))[:limit]

def default_strategy(report):
    actions = {"flood": "Activate evacuation and shelter readiness, move water and medical supplies to safe access points, and monitor road closures.", "earthquake": "Conduct rapid search-and-rescue and structural safety assessments, establish medical triage, and keep people away from damaged buildings.", "cyclone": "Issue evacuation alerts, secure shelters and emergency communications, and pre-position food, water, and medical teams before landfall.", "drought": "Prioritise safe water distribution, protect vulnerable populations, and coordinate food and health support.", "wildfire": "Create evacuation perimeters, protect critical infrastructure, monitor wind direction, and position medical and firefighting resources safely."}
    urgency = "Treat this as an immediate response priority." if severity_for_score(impact_for(report)[0]) == "High" else "Continue reassessing conditions and escalate resources if impact increases."
    return f"{actions.get(report.disaster_type.casefold(), 'Verify the incident, conduct a rapid needs assessment, protect affected people, and stage essential relief resources.')} {urgency}"

def similar_reports(report, candidates, limit):
    impact = impact_for(report)[0]; results = []
    for candidate in candidates:
        if candidate.id == report.id: continue
        candidate_impact = impact_for(candidate)[0]
        score = (50 if candidate.disaster_type.casefold() == report.disaster_type.casefold() else 0) + max(0, 25 - abs(candidate.magnitude - report.magnitude) * 3) + max(0, 25 - abs(candidate_impact - impact) * .5)
        results.append({"report_id": candidate.id, "disaster_type": candidate.disaster_type, "magnitude": candidate.magnitude, "affected_population": candidate.affected_population, "impact_score": candidate_impact, "similarity_score": round(score, 2), "created_at": candidate.created_at})
    return sorted(results, key=lambda item: (-item["similarity_score"], item["created_at"]))[:limit]
