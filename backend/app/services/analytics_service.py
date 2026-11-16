from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import log10


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def estimated_impact_score(report) -> float:
    return round(min(min(report.magnitude / 15, 1) * 40 + min(log10(max(report.affected_population, 1)) / 7, 1) * 35 + min(max(report.weather_score, 0), 1) * 25, 100), 2)


def impact_for(report) -> tuple[float, str]:
    return (round(float(report.predicted_impact_score), 2), "predicted") if report.predicted_impact_score is not None else (estimated_impact_score(report), "estimated")


def severity_for_score(score: float) -> str:
    return "High" if score >= 70 else "Moderate" if score >= 31 else "Low"


def build_trend_analytics(reports, days: int) -> dict:
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    reports = [r for r in reports if _utc(r.created_at) >= start_date]
    def summarize(group):
        predictions = [impact_for(r)[0] for r in group if r.predicted_impact_score is not None]
        return (round(sum(predictions) / len(predictions), 2) if predictions else None, sum(r.affected_population for r in group))
    types, dates = defaultdict(list), defaultdict(list)
    for report in reports:
        types[report.disaster_type].append(report); dates[_utc(report.created_at).date().isoformat()].append(report)
    breakdown = [{"disaster_type": key, "report_count": len(group), "average_impact_score": summarize(group)[0], "total_affected_population": summarize(group)[1]} for key, group in types.items()]
    breakdown.sort(key=lambda item: (-item["report_count"], item["disaster_type"]))
    average, population = summarize(reports)
    return {"period_days": days, "start_date": start_date, "end_date": end_date, "total_reports": len(reports), "predicted_reports": sum(r.predicted_impact_score is not None for r in reports), "average_impact_score": average, "total_affected_population": population, "most_frequent_disaster_type": breakdown[0]["disaster_type"] if breakdown else None, "disaster_type_breakdown": breakdown, "daily_trend": [{"period": day, "report_count": len(group), "average_impact_score": summarize(group)[0], "total_affected_population": summarize(group)[1]} for day, group in sorted(dates.items())]}


def priority_item(report, current_status: str) -> dict:
    impact, source = impact_for(report); magnitude = round(min(report.magnitude / 15, 1) * 100, 2)
    return {"report_id": report.id, "disaster_type": report.disaster_type, "magnitude": report.magnitude, "affected_population": report.affected_population, "impact_score": impact, "impact_score_source": source, "severity_score": magnitude, "severity": severity_for_score(impact), "priority_score": round(impact * .75 + magnitude * .25, 2), "current_status": current_status, "created_at": report.created_at}
