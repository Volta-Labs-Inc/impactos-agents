"""A2UI v0.9.1 message schema and the eight-component ShadCN catalogue.

A deterministic, standard-library validator for the A2UI *server-to-client*
messages the ``brief`` command emits. It is a faithful Python port of two things
that travel with the pinned renderer:

* the v0.9 server-to-client message envelope
  (``@a2ui/web_core`` 0.10.6, ``src/v0_9/schemas/server_to_client.json`` and
  ``common_types.json``); and
* the eight-component ShadCN catalogue defined in the A2UI POC
  (``~/Development/A2UI/src/a2ui/components``), whose per-component ``zod``
  schemas the renderer enforces at runtime.

The validator exists so the CLI can refuse to write an invalid blueprint (the
skill shows an error, never a blank page) and so ``test_brief.py`` can prove the
generated messages satisfy the schema and the catalogue without a Node runtime.
The renderer's Vitest smoke test remains the ground-truth check: it feeds the
same fixture through the real ``MessageProcessor`` and catalogue.

The protocol is a point release (``v0.9.1``) of the ``v0.9`` message family; the
runtime processor does not pin the message ``version`` string, so both are
accepted here.
"""

from __future__ import annotations

from typing import Any, Dict, List

# The catalogue id the renderer registers (see renderer/src/a2ui/catalog-id.ts
# and the POC). createSurface.catalogId must match it exactly.
CATALOG_ID = "https://a2ui.local/catalogs/shadcn/v1.json"

# The protocol the pinned renderer speaks. brief emits this; the v0.9 family is
# accepted on read.
PROTOCOL_VERSION = "v0.9.1"
ACCEPTED_VERSIONS = {"v0.9", "v0.9.1"}

UPDATE_KEYS = ("createSurface", "updateComponents", "updateDataModel", "deleteSurface")

# Per-component property contract, mirroring the catalogue's zod schemas. Each
# entry lists the required and optional property names, any enum-constrained
# props, the dynamic-typed props, and how the component references children.
#   dyn_string: value is a literal string or a {"path": str} data binding.
#   dyn_value:  value is a literal (str/number/bool/array) or a {"path": str}.
_CATALOG: Dict[str, Dict[str, Any]] = {
    "Text": {
        "required": ["text"],
        "optional": ["variant"],
        "dyn_string": ["text"],
        "enums": {"variant": ["h1", "h2", "h3", "body", "muted"]},
    },
    "Card": {
        "required": ["child"],
        "optional": [],
        "child_ref": "child",  # single component id
    },
    "Button": {
        "required": ["label"],
        "optional": ["variant", "action"],
        "dyn_string": ["label"],
        "enums": {"variant": ["default", "primary", "outline", "ghost"]},
        "action": ["action"],
    },
    "Input": {
        "required": ["label"],
        "optional": ["value", "placeholder"],
        "dyn_string": ["label", "value", "placeholder"],
    },
    "Select": {
        "required": ["label", "options"],
        "optional": ["value", "placeholder"],
        "dyn_string": ["label", "value", "placeholder"],
        "options": "options",
    },
    "Table": {
        "required": ["columns", "rows"],
        "optional": ["caption"],
        "dyn_string": ["caption"],
        "dyn_value": ["rows"],
        "columns": "columns",
    },
    "Column": {
        "required": ["children"],
        "optional": ["justify", "align"],
        "children_ref": "children",  # child list
        "enums": {
            "justify": ["start", "center", "end", "spaceBetween", "spaceAround", "spaceEvenly", "stretch"],
            "align": ["start", "center", "end", "stretch"],
        },
    },
    "Row": {
        "required": ["children"],
        "optional": ["justify", "align"],
        "children_ref": "children",
        "enums": {
            "justify": ["start", "center", "end", "spaceBetween", "spaceAround", "spaceEvenly", "stretch"],
            "align": ["start", "center", "end", "stretch"],
        },
    },
}

CATALOG_COMPONENTS = tuple(_CATALOG.keys())


def _is_dyn_string(value: Any) -> bool:
    if isinstance(value, str):
        return True
    return isinstance(value, dict) and set(value.keys()) == {"path"} and isinstance(value["path"], str)


def _is_dyn_value(value: Any) -> bool:
    if isinstance(value, (str, int, float, bool, list)):
        return True
    return isinstance(value, dict) and set(value.keys()) == {"path"} and isinstance(value["path"], str)


def _validate_component(comp: Any, defined: Dict[str, str], child_refs: List[str], errors: List[str]) -> None:
    where = "component"
    if not isinstance(comp, dict):
        errors.append(f"{where}: not an object: {comp!r}")
        return
    comp_id = comp.get("id")
    name = comp.get("component")
    if not isinstance(comp_id, str) or not comp_id:
        errors.append(f"{where}: missing string 'id'")
        return
    where = f"component {comp_id!r}"
    if comp_id in defined:
        errors.append(f"{where}: duplicate id")
    if not isinstance(name, str) or name not in _CATALOG:
        errors.append(f"{where}: unknown component type {name!r} (not in catalogue {list(_CATALOG)})")
        defined[comp_id] = name if isinstance(name, str) else "?"
        return
    defined[comp_id] = name
    spec = _CATALOG[name]

    props = {k: v for k, v in comp.items() if k not in ("id", "component", "accessibility")}
    allowed = set(spec["required"]) | set(spec.get("optional", []))
    for key in props:
        if key not in allowed:
            errors.append(f"{where} ({name}): unexpected property {key!r}")
    for key in spec["required"]:
        if key not in props:
            errors.append(f"{where} ({name}): missing required property {key!r}")

    for key in spec.get("dyn_string", []):
        if key in props and not _is_dyn_string(props[key]):
            errors.append(f"{where} ({name}): property {key!r} must be a string or {{'path': ...}}")
    for key in spec.get("dyn_value", []):
        if key in props and not _is_dyn_value(props[key]):
            errors.append(f"{where} ({name}): property {key!r} must be a literal or {{'path': ...}}")
    for key, choices in spec.get("enums", {}).items():
        if key in props and props[key] not in choices:
            errors.append(f"{where} ({name}): property {key!r} must be one of {choices}")

    # Child references.
    if "child_ref" in spec:
        ref = props.get(spec["child_ref"])
        if not isinstance(ref, str):
            errors.append(f"{where} ({name}): {spec['child_ref']!r} must be a component id string")
        else:
            child_refs.append(ref)
    if "children_ref" in spec:
        children = props.get(spec["children_ref"])
        if isinstance(children, list):
            for child in children:
                if not isinstance(child, str):
                    errors.append(f"{where} ({name}): children must be component id strings")
                else:
                    child_refs.append(child)
        elif isinstance(children, dict):
            if set(children.keys()) != {"componentId", "path"}:
                errors.append(f"{where} ({name}): dynamic children must be {{componentId, path}}")
            else:
                child_refs.append(children["componentId"])
        else:
            errors.append(f"{where} ({name}): 'children' must be a list of ids or a {{componentId, path}} template")

    # Structured props.
    if spec.get("options") and "options" in props:
        options = props["options"]
        if not isinstance(options, list) or not options:
            errors.append(f"{where} ({name}): 'options' must be a non-empty array")
        else:
            for opt in options:
                if not (isinstance(opt, dict) and _is_dyn_string(opt.get("label")) and isinstance(opt.get("value"), str)):
                    errors.append(f"{where} ({name}): each option needs a label and a string value")
    if spec.get("columns") and "columns" in props:
        columns = props["columns"]
        if not isinstance(columns, list) or not columns:
            errors.append(f"{where} ({name}): 'columns' must be a non-empty array")
        else:
            for col in columns:
                if not (isinstance(col, dict) and isinstance(col.get("key"), str) and _is_dyn_string(col.get("label"))):
                    errors.append(f"{where} ({name}): each column needs a string key and a label")


def validate_messages(messages: Any) -> List[str]:
    """Return a list of human-readable errors; an empty list means valid."""
    errors: List[str] = []
    if not isinstance(messages, list) or not messages:
        return ["messages must be a non-empty array"]

    surfaces: Dict[str, Dict[str, str]] = {}  # surfaceId -> {component id: type}
    surface_child_refs: Dict[str, List[str]] = {}

    for index, message in enumerate(messages):
        prefix = f"message[{index}]"
        if not isinstance(message, dict):
            errors.append(f"{prefix}: not an object")
            continue
        version = message.get("version")
        if version not in ACCEPTED_VERSIONS:
            errors.append(f"{prefix}: version must be one of {sorted(ACCEPTED_VERSIONS)}, got {version!r}")
        present = [k for k in UPDATE_KEYS if k in message]
        extra = [k for k in message if k not in ("version",) and k not in UPDATE_KEYS]
        if extra:
            errors.append(f"{prefix}: unexpected keys {extra}")
        if len(present) != 1:
            errors.append(f"{prefix}: exactly one of {list(UPDATE_KEYS)} required, found {present}")
            continue
        kind = present[0]
        payload = message[kind]
        if not isinstance(payload, dict):
            errors.append(f"{prefix}.{kind}: not an object")
            continue

        if kind == "createSurface":
            surface_id = payload.get("surfaceId")
            catalog_id = payload.get("catalogId")
            if not isinstance(surface_id, str) or not surface_id:
                errors.append(f"{prefix}.createSurface: missing 'surfaceId'")
            if catalog_id != CATALOG_ID:
                errors.append(f"{prefix}.createSurface: catalogId must be {CATALOG_ID!r}, got {catalog_id!r}")
            for key in payload:
                if key not in ("surfaceId", "catalogId", "theme", "sendDataModel"):
                    errors.append(f"{prefix}.createSurface: unexpected key {key!r}")
            if isinstance(surface_id, str) and surface_id:
                if surface_id in surfaces:
                    errors.append(f"{prefix}.createSurface: surface {surface_id!r} already created")
                surfaces.setdefault(surface_id, {})
                surface_child_refs.setdefault(surface_id, [])

        elif kind == "updateComponents":
            surface_id = payload.get("surfaceId")
            components = payload.get("components")
            if surface_id not in surfaces:
                errors.append(f"{prefix}.updateComponents: surface {surface_id!r} was not created")
            if not isinstance(components, list) or not components:
                errors.append(f"{prefix}.updateComponents: 'components' must be a non-empty array")
                continue
            defined = surfaces.setdefault(surface_id if isinstance(surface_id, str) else "?", {})
            child_refs = surface_child_refs.setdefault(surface_id if isinstance(surface_id, str) else "?", [])
            for comp in components:
                _validate_component(comp, defined, child_refs, errors)

        elif kind == "updateDataModel":
            surface_id = payload.get("surfaceId")
            if surface_id not in surfaces:
                errors.append(f"{prefix}.updateDataModel: surface {surface_id!r} was not created")
            for key in payload:
                if key not in ("surfaceId", "path", "value"):
                    errors.append(f"{prefix}.updateDataModel: unexpected key {key!r}")

        elif kind == "deleteSurface":
            surface_id = payload.get("surfaceId")
            if not isinstance(surface_id, str) or not surface_id:
                errors.append(f"{prefix}.deleteSurface: missing 'surfaceId'")

    # Per-surface structural checks: one root, all child refs defined.
    for surface_id, defined in surfaces.items():
        if not defined:
            continue
        if "root" not in defined:
            errors.append(f"surface {surface_id!r}: no component with id 'root'")
        for ref in surface_child_refs.get(surface_id, []):
            if ref not in defined:
                errors.append(f"surface {surface_id!r}: child reference {ref!r} is not defined")

    return errors
