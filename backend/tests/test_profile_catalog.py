"""The profile option catalogue and the migration of hand-written profiles.

What these lock down:

* the catalogue covers every section the picker renders, and every option id is
  a slug (the vocabulary the n8n workflows read);
* saving through the API produces the option-id JSON the user never has to see;
* an old profile written as free text or comma-separated strings still opens,
  and nothing the user typed is ever dropped on the floor.
"""
from __future__ import annotations

import pytest

from app.services import profile_catalog as pc
from app.services import profiles as svc

_PASSWORD = "Correct9Horse"


def test_every_section_the_ui_needs_is_present():
    keys = [s.key for s in pc.SECTIONS]
    assert keys == [
        "formacion",
        "sector",
        "objetivo_profesional",
        "ubicacion",
        "experiencia_nivel",
        "intereses",
        "preferencias_laborales",
        "preferencias_noticias",
        "marca_personal",
        "automatizaciones",
    ]


def test_option_ids_are_slugs():
    """A label with an accent or a space would stop matching modules.json."""
    for section in pc.SECTIONS:
        for f in section.fields:
            for option in f.options:
                assert option.id == option.id.lower(), option.id
                assert option.id.replace("_", "").isalnum(), option.id
                assert option.label.strip(), option.id


def test_option_ids_are_unique_within_a_field():
    for section in pc.SECTIONS:
        for f in section.fields:
            ids = [o.id for o in f.options]
            assert len(ids) == len(set(ids)), f.key


def test_the_four_shipped_automations_are_toggles():
    section = next(s for s in pc.SECTIONS if s.key == "automatizaciones")
    assert [f.path[-1] for f in section.fields] == [
        "agenda",
        "laboral",
        "noticias",
        "marca_personal",
    ]
    assert all(f.kind == "toggle" for f in section.fields)
    assert all(f.hint for f in section.fields), "each card needs its explanation"


def test_fields_write_into_the_documented_dimensions():
    """The picker must not invent new configuration keys."""
    top_level = {f.path[0] for s in pc.SECTIONS for f in s.fields}
    known = set(svc.PROFILE_DIMENSIONS) | {"formacion_otra", "ubicacion_otra"}
    assert top_level <= known, top_level - known


def test_required_sections_match_the_backend_rule():
    """The progress bar and the PROFILE monitor tile must agree."""
    required = set(pc.as_dict()["required_sections"])
    graded = set()
    for _label, keys in svc.REQUIRED_PROFILE_FIELDS:
        graded.update(keys)
    assert required <= graded


# ------------------------------------------------------------- migration ----


def test_free_text_maps_onto_option_ids():
    out = pc.normalise_configuration({"formacion": "Ingeniería en Organización Industrial"})
    assert out == {"formacion": ["ingenieria_organizacion_industrial"]}


def test_comma_separated_legacy_values_become_a_list():
    out = pc.normalise_configuration({"sector": "tecnologia, Automoción"})
    assert out == {"sector": ["tecnologia", "automocion"]}


def test_unknown_values_are_kept_not_dropped():
    out = pc.normalise_configuration({"intereses": ["Automatización", "algo que inventé"]})
    assert out == {"intereses": ["automatizacion", "algo que inventé"]}


def test_unknown_keys_pass_through_untouched():
    out = pc.normalise_configuration({"campo_privado": {"a": 1}})
    assert out == {"campo_privado": {"a": 1}}


def test_grouped_fields_are_normalised_inside_the_group():
    out = pc.normalise_configuration(
        {"preferencias_laborales": {"salario_minimo": "40.000 €", "tipo_empresa": "Startup"}}
    )
    assert out["preferencias_laborales"]["salario_minimo"] == "40k"
    assert out["preferencias_laborales"]["tipo_empresa"] == ["startup"]


def test_toggles_are_coerced_to_booleans():
    out = pc.normalise_configuration({"automatizaciones": {"agenda": "yes", "laboral": ""}})
    assert out["automatizaciones"] == {"agenda": True, "laboral": False}


def test_duplicates_collapse_after_mapping():
    """"Automatización" and "automatizacion" are the same option."""
    out = pc.normalise_configuration({"intereses": ["Automatización", "automatizacion"]})
    assert out == {"intereses": ["automatizacion"]}


def test_empty_configuration_stays_empty():
    assert pc.normalise_configuration({}) == {}
    assert pc.normalise_configuration(None) == {}


# ------------------------------------------------------------------ API ----


def _login(client) -> str:
    client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "username": "admin", "password": _PASSWORD},
    )
    r = client.post("/api/auth/login", json={"identifier": "admin", "password": _PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_catalog_endpoint_is_public_and_complete(client):
    r = client.get("/api/profiles/catalog")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["sections"]) == 10
    formacion = next(s for s in body["sections"] if s["key"] == "formacion")
    assert formacion["question"] == "¿Cuál es tu formación?"
    field = formacion["fields"][0]
    assert field["kind"] == "multi"
    assert {"id": "ingenieria_organizacion_industrial", "label": "Ingeniería en Organización Industrial"} in field["options"]
    # "Otra" reveals a free-text box instead of making the user type everything
    assert field["free_text_trigger"] == "otra"
    assert field["free_text_path"] == ["formacion_otra"]


def test_saving_selections_produces_option_id_json(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/profiles",
        headers=headers,
        json={
            "name": "Alex",
            "make_primary": True,
            "configuration": {
                "formacion": ["ingenieria_organizacion_industrial"],
                "sector": ["industria_manufactura", "tecnologia", "inteligencia_artificial"],
                "objetivo_profesional": ["graduate_program", "alta_proyeccion"],
                "ubicacion": ["barcelona", "madrid", "remoto"],
                "modalidad": ["hibrido", "remoto"],
                "experiencia_nivel": ["graduate", "junior"],
                "intereses": ["automatizacion", "supply_chain", "inteligencia_artificial"],
                "automatizaciones": {"agenda": True, "laboral": True, "noticias": False, "marca_personal": False},
            },
        },
    )
    assert r.status_code in (200, 201), r.text
    config = r.json()["configuration"]
    assert config["sector"] == ["industria_manufactura", "tecnologia", "inteligencia_artificial"]
    assert config["automatizaciones"]["agenda"] is True
    assert config["automatizaciones"]["noticias"] is False

    # and that is enough to make the profile count as configured
    completeness = client.get("/api/profiles/completeness", headers=headers).json()
    assert completeness["configured"] is True


def test_an_old_hand_written_profile_is_migrated_on_save(client):
    """Legacy profiles must not need a destructive data migration: re-saving
    one through the API converts it in place."""
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/profiles",
        headers=headers,
        json={
            "name": "Antiguo",
            "configuration": {
                "formacion": "Ingeniería Industrial",
                "sector": "tecnologia, Automoción",
                "notas_personales": "no tocar",
            },
        },
    )
    assert r.status_code in (200, 201), r.text
    config = r.json()["configuration"]
    assert config["formacion"] == ["ingenieria_industrial"]
    assert config["sector"] == ["tecnologia", "automocion"]
    assert config["notas_personales"] == "no tocar", "unknown keys must survive"


def test_editing_a_profile_keeps_the_option_vocabulary(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/profiles",
        headers=headers,
        json={"name": "Alex", "configuration": {"sector": ["tecnologia"]}},
    ).json()

    r = client.patch(
        f"/api/profiles/{created['id']}",
        headers=headers,
        json={"configuration": {"sector": ["Tecnología", "Gaming"]}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["configuration"]["sector"] == ["tecnologia", "gaming"]


@pytest.mark.parametrize("bad", [{}, {"intereses": []}, {"sector": ""}])
def test_an_empty_profile_is_never_complete(client, bad):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/profiles", headers=headers, json={"name": "Vacio", "configuration": bad})
    completeness = client.get("/api/profiles/completeness", headers=headers).json()
    assert completeness["configured"] is False
