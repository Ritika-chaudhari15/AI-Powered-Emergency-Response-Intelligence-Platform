"""Database-backed translation cache with local IndicTrans2 as the cache-miss provider."""

import json
from collections import OrderedDict
from hashlib import sha256
from pathlib import Path
from threading import Lock

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import TranslationKey, TranslationValue
from app.services.indictrans_local_service import INDIC_LANGUAGE_CODES, get_local_indictrans_engine

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = {"en": "English", **{code: name for code, (name, _) in INDIC_LANGUAGE_CODES.items()}}

# English source keys are seeded into the database. The model generates and caches every non-English value.
CORE_STATIC_CATALOG = {
    "app.name": "AI-Based Disaster Response Management System for Resource Allocation and Relief Coordination",
    "nav.dashboard": "Dashboard", "nav.disaster_reports": "Disaster Reports", "nav.warehouses": "Warehouses",
    "nav.notifications": "Notifications", "nav.profile": "Profile", "auth.login": "Login", "auth.logout": "Logout",
    "action.submit": "Submit", "action.cancel": "Cancel", "action.save": "Save", "action.retry": "Retry",
    "status.reported": "Reported", "status.assessed": "Assessed", "status.partially_allocated": "Partially Allocated",
    "status.allocated": "Allocated", "status.dispatched": "Dispatched", "status.completed": "Completed",
    "disaster.earthquake": "Earthquake", "disaster.flood": "Flood", "disaster.cyclone": "Cyclone",
    "disaster.drought": "Drought", "disaster.wildfire": "Wildfire",
    "auth.hero_brand": "AI-Based Disaster Response Management System", "auth.hero_eyebrow": "AI-powered resilience platform",
    "auth.hero_title": "Turn urgency into", "auth.hero_emphasis": "coordinated action.",
    "auth.hero_description": "One operational command center for disaster intelligence, resource logistics, and field response.",
    "auth.incident_readiness": "Incident readiness", "auth.indian_languages": "Indian languages", "auth.operations_signal": "Operations signal",
    "auth.secure_access": "Secure operations access", "auth.please_wait": "Please wait…", "auth.already_have_account": "Already have an account?",
    "auth.new_to_responda": "New to Responda?", "auth.full_name_placeholder": "John Doe", "auth.email_placeholder": "you@example.com",
    "knowledge.subtitle_create": "Capture field practices and lessons for future responses.", "knowledge.add": "Add knowledge",
    "knowledge.title_label": "Title", "knowledge.title_placeholder": "Flood evacuation checkpoint plan", "knowledge.entry_type": "Entry type",
    "knowledge.disaster_type_optional": "Disaster type (optional)", "knowledge.severity_optional": "Severity (optional)",
    "knowledge.guidance": "Guidance or lesson", "knowledge.guidance_placeholder": "Describe the field action, outcome, and what should be repeated or avoided.",
    "knowledge.tags": "Tags (comma separated)", "knowledge.tags_placeholder": "evacuation, medical, road-access", "knowledge.save": "Save knowledge",
    "knowledge.empty_create": "No knowledge entries yet. Add a field practice, past response, or lesson learned above.",
    "profile.eyebrow": "Account settings", "profile.title": "My profile", "profile.subtitle": "Manage your personal information and account preferences.",
    "profile.personal_information": "Personal information", "profile.email_unchangeable": "Your email address cannot be changed.",
    "profile.active_account": "Active account", "profile.member_since": "Member since", "profile.save_changes": "Save changes",
    "teams.no_vehicle_details": "No vehicle details", "teams.untagged": "Untagged", "ui.loading": "Loading operations data…",
    "skill.medical_support": "Medical support", "skill.radio_operations": "Radio operations", "skill.logistics": "Logistics", "skill.search_and_rescue": "Search and rescue",
    "skill.first_aid": "First aid", "skill.medical_response": "Medical response", "skill.water_rescue": "Water rescue", "skill.logistics_and_relief": "Logistics and relief",
}

_CATALOG_PATH = Path(__file__).resolve().parents[1] / "translation_catalog.json"
with _CATALOG_PATH.open(encoding="utf-8") as catalog_file:
    STATIC_CATALOG = {**CORE_STATIC_CATALOG, **json.load(catalog_file)}


class _MemoryTranslationCache:
    def __init__(self, capacity: int = 4096):
        self.capacity, self.values, self.lock = capacity, OrderedDict(), Lock()

    def get(self, key: tuple[str, str]) -> str | None:
        with self.lock:
            value = self.values.get(key)
            if value is not None:
                self.values.move_to_end(key)
            return value

    def put(self, key: tuple[str, str], value: str) -> None:
        with self.lock:
            self.values[key] = value
            self.values.move_to_end(key)
            if len(self.values) > self.capacity:
                self.values.popitem(last=False)


memory_cache = _MemoryTranslationCache()


def resolve_locale(override: str | None, accept_language: str | None) -> str:
    candidates = [override] if override else []
    if accept_language:
        candidates.extend(part.split(";", 1)[0].strip() for part in accept_language.split(","))
    for candidate in candidates:
        if candidate:
            code = candidate.lower().replace("_", "-").split("-", 1)[0]
            if code in SUPPORTED_LOCALES:
                return code
    return DEFAULT_LOCALE


def ensure_catalog(db: Session) -> None:
    """Persist source keys once; existing translations are never overwritten."""
    for key, source_text in STATIC_CATALOG.items():
        if db.scalar(select(TranslationKey.id).where(TranslationKey.key == key)) is None:
            db.add(TranslationKey(key=key, source_text=source_text))
    db.commit()


def _generated_key(source_text: str) -> str:
    return f"api.{sha256(source_text.encode('utf-8')).hexdigest()}"


def _get_or_create_key(db: Session, key: str, source_text: str) -> TranslationKey:
    entry = db.scalar(select(TranslationKey).where(TranslationKey.key == key))
    if entry:
        return entry
    entry = TranslationKey(key=key, source_text=source_text)
    db.add(entry)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return db.scalar(select(TranslationKey).where(TranslationKey.key == key))
    return entry


def translate(db: Session, key: str, source_text: str, locale: str) -> str:
    """Use RAM cache, then DB cache, and only then local IndicTrans2 inference."""
    if locale == DEFAULT_LOCALE:
        return source_text
    cache_key = (key, locale)
    if cached := memory_cache.get(cache_key):
        return cached
    entry = _get_or_create_key(db, key, source_text)
    cached_value = db.scalar(select(TranslationValue.text).where(
        TranslationValue.translation_key_id == entry.id, TranslationValue.locale == locale
    ))
    if cached_value:
        memory_cache.put(cache_key, cached_value)
        return cached_value
    translated = get_local_indictrans_engine().translate_batch([entry.source_text], locale)[0]
    db.add(TranslationValue(translation_key_id=entry.id, locale=locale, text=translated, generated_by="indictrans2"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        translated = db.scalar(select(TranslationValue.text).where(
            TranslationValue.translation_key_id == entry.id, TranslationValue.locale == locale
        ))
    memory_cache.put(cache_key, translated)
    return translated


def translate_api_detail(db: Session, detail: object, locale: str) -> object:
    if isinstance(detail, str):
        return translate(db, _generated_key(detail), detail, locale)
    if isinstance(detail, dict):
        return {key: translate_api_detail(db, value, locale) for key, value in detail.items()}
    if isinstance(detail, list):
        return [translate_api_detail(db, value, locale) for value in detail]
    return detail


def get_bundle(db: Session, locale: str) -> dict[str, str]:
    """Resolve a complete UI bundle with one batched model call for all cache misses."""
    ensure_catalog(db)
    entries = list(db.scalars(select(TranslationKey).where(TranslationKey.key.in_(STATIC_CATALOG))))
    if locale == DEFAULT_LOCALE:
        return {entry.key: entry.source_text for entry in entries}

    database_values = {
        key: text for key, text in db.execute(
            select(TranslationKey.key, TranslationValue.text)
            .join(TranslationValue, TranslationValue.translation_key_id == TranslationKey.id)
            .where(TranslationKey.key.in_(STATIC_CATALOG), TranslationValue.locale == locale)
        )
    }
    bundle: dict[str, str] = {}
    missing: list[TranslationKey] = []
    for entry in entries:
        cache_key = (entry.key, locale)
        if cached := memory_cache.get(cache_key):
            bundle[entry.key] = cached
        elif cached := database_values.get(entry.key):
            memory_cache.put(cache_key, cached)
            bundle[entry.key] = cached
        else:
            missing.append(entry)

    if missing:
        generated = get_local_indictrans_engine().translate_batch([entry.source_text for entry in missing], locale)
        for entry, translated in zip(missing, generated, strict=True):
            db.add(TranslationValue(
                translation_key_id=entry.id, locale=locale, text=translated, generated_by="indictrans2"
            ))
            memory_cache.put((entry.key, locale), translated)
            bundle[entry.key] = translated
        try:
            db.commit()
        except IntegrityError:
            # Another API worker populated the same cache entries first.
            db.rollback()
            return get_bundle(db, locale)
    return bundle
