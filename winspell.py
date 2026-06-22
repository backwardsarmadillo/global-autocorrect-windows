"""Thin wrapper over the Windows Spell Checking API (ISpellChecker) -- the same
engine that powers the red-squiggle suggestions across Windows apps. We use it
to generate correction candidates (Microsoft's dictionary is far better than a
static frequency list); the caller re-ranks them with context and keyboard
geometry.

Everything degrades gracefully: if comtypes is missing or the COM call fails,
suggest() returns None so the caller can fall back to the bundled SymSpell
dictionary.
"""
import threading

try:
    from ctypes import POINTER, c_int, c_ulong, c_wchar_p
    import comtypes
    from comtypes import (
        GUID,
        IUnknown,
        COMMETHOD,
        HRESULT,
        CoCreateInstance,
        CLSCTX_INPROC_SERVER,
    )

    _COMTYPES_OK = True
except Exception:  # pragma: no cover - only when comtypes unavailable
    _COMTYPES_OK = False


if _COMTYPES_OK:

    class IEnumString(IUnknown):
        _iid_ = GUID("{00000101-0000-0000-C000-000000000046}")
        _methods_ = [
            COMMETHOD(
                [], HRESULT, "RemoteNext",
                (["in"], c_ulong, "celt"),
                (["out"], POINTER(c_wchar_p), "rgelt"),
                (["out"], POINTER(c_ulong), "pceltFetched"),
            ),
            COMMETHOD([], HRESULT, "Skip", (["in"], c_ulong, "celt")),
            COMMETHOD([], HRESULT, "Reset"),
            COMMETHOD([], HRESULT, "Clone",
                      (["out"], POINTER(POINTER(IUnknown)), "ppenum")),
        ]

    class IEnumSpellingError(IUnknown):
        _iid_ = GUID("{803E3BD4-2828-4410-8290-418D1D73C762}")
        # Next yields the next spelling error, or NULL when there are none. We
        # only care whether at least one exists, so the error object itself is
        # left as a bare IUnknown.
        _methods_ = [
            COMMETHOD([], HRESULT, "Next",
                      (["out"], POINTER(POINTER(IUnknown)), "value")),
        ]

    class ISpellChecker(IUnknown):
        _iid_ = GUID("{B6FD0B71-E2BC-4653-8D05-F197E412770B}")
        _methods_ = [
            COMMETHOD([], HRESULT, "get_LanguageTag",
                      (["out"], POINTER(c_wchar_p), "value")),
            COMMETHOD([], HRESULT, "Check",
                      (["in"], c_wchar_p, "text"),
                      (["out"], POINTER(POINTER(IEnumSpellingError)), "value")),
            COMMETHOD([], HRESULT, "Suggest",
                      (["in"], c_wchar_p, "word"),
                      (["out"], POINTER(POINTER(IEnumString)), "value")),
        ]

    class ISpellCheckerFactory(IUnknown):
        _iid_ = GUID("{8E018A9D-2415-4677-BF08-794EA61F94BB}")
        _methods_ = [
            COMMETHOD([], HRESULT, "get_SupportedLanguages",
                      (["out"], POINTER(POINTER(IEnumString)), "value")),
            COMMETHOD([], HRESULT, "IsSupported",
                      (["in"], c_wchar_p, "languageTag"),
                      (["out"], POINTER(c_int), "value")),
            COMMETHOD([], HRESULT, "CreateSpellChecker",
                      (["in"], c_wchar_p, "languageTag"),
                      (["out"], POINTER(POINTER(ISpellChecker)), "value")),
        ]

    _CLSID_SpellCheckerFactory = GUID("{7AB36653-1796-484B-BDFA-E74F1DB7C1DC}")


# COM apartments are per-thread, so cache the checker in thread-local storage and
# create it lazily in whichever thread first asks (the keyboard listener thread).
_local = threading.local()


def _get_checker(language="en-US"):
    if not _COMTYPES_OK:
        return None
    if getattr(_local, "failed", False):
        return None
    checker = getattr(_local, "checker", None)
    if checker is not None:
        return checker
    try:
        comtypes.CoInitialize()
        factory = CoCreateInstance(
            _CLSID_SpellCheckerFactory,
            interface=ISpellCheckerFactory,
            clsctx=CLSCTX_INPROC_SERVER,
        )
        if not factory.IsSupported(language):
            _local.failed = True
            return None
        _local.checker = factory.CreateSpellChecker(language)
        return _local.checker
    except Exception:
        _local.failed = True
        return None


def available():
    return _get_checker() is not None


def suggest(word, limit=8):
    """Return Windows' ordered suggestions for `word`.

    None  -> the API is unavailable (caller should fall back).
    []    -> Windows considers the word correctly spelled.
    [...] -> ordered candidates, best first.
    """
    checker = _get_checker()
    if checker is None:
        return None
    try:
        # Authoritative misspelling test: Check() reports actual spelling errors
        # (the red squiggles). Suggest() alone is unreliable because it returns
        # alternatives even for correctly spelled words.
        errors = checker.Check(word)
        if not errors.Next():
            return []  # Windows considers it correctly spelled
    except Exception:
        return None
    try:
        enum = checker.Suggest(word)
        out = []
        while len(out) < limit:
            item, fetched = enum.RemoteNext(1)
            if not fetched:
                break
            if item and item.lower() != word.lower():
                out.append(item)
        return out
    except Exception:
        return None
