# Standard gettext Framework for Internationalization

## Context
The application relied on a custom in-code dictionary (`TRANSLATIONS = {'en': {...}, 'ar': {...}}`) and an ad-hoc `Translator` class with custom lookup logic. This hardcoded strings directly in Python code and prevented standard translation tooling and localization workflows.

## Decision
We decided to replace the custom in-code translation dictionary with Python's standard library `gettext` module:
- Standard `gettext` catalog integration (`locale/`, `.po`/`.mo` files or built-in fallback catalogs).
- Expose the canonical `_("string")` translation function across both domain and presentation layers.
- Remove the manual dictionary lookup and redundant translation helper methods.

## Rationale & Trade-offs
Adopting `gettext` replaces home-grown dictionary indexing with the industry-standard GNU gettext internationalization framework already included in Python's standard library (zero external dependencies). It decouples translation catalogs from application source code and allows automated string extraction via `xgettext` or `pygettext`.
