import { beforeEach, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { PersonalisePage } from "./PersonalisePage";
import { installFetchStub, renderWithProviders, sampleUser } from "@/test/utils";
import { setSession } from "@/api/tokenStore";

/**
 * Personalisation is a picker, not a form. These tests pin the behaviours that
 * make that true: clicking writes option ids, the user never sees or types
 * JSON, an older hand-written profile still opens without losing anything, and
 * an empty profile cannot be saved.
 */

const PROFILE_ID = "22222222-2222-2222-2222-222222222222";

const catalog = {
  sections: [
    {
      key: "formacion",
      title: "Formación",
      question: "¿Cuál es tu formación?",
      description: "",
      fields: [
        {
          key: "formacion",
          path: ["formacion"],
          label: "Formación",
          kind: "multi",
          hint: "",
          options: [
            { id: "ingenieria_organizacion_industrial", label: "Ingeniería en Organización Industrial" },
            { id: "ingenieria_informatica", label: "Ingeniería Informática" },
            { id: "otra", label: "Otra" },
          ],
          free_text_trigger: "otra",
          free_text_path: ["formacion_otra"],
          free_text_label: "¿Cuál?",
        },
      ],
    },
    {
      key: "sector",
      title: "Sector",
      question: "¿En qué sectores te interesa trabajar?",
      description: "",
      fields: [
        {
          key: "sector",
          path: ["sector"],
          label: "Sectores",
          kind: "multi",
          hint: "",
          options: [
            { id: "industria_manufactura", label: "Industria" },
            { id: "tecnologia", label: "Tecnología" },
            { id: "inteligencia_artificial", label: "Inteligencia Artificial" },
          ],
          free_text_trigger: "",
          free_text_path: [],
          free_text_label: "",
        },
      ],
    },
    {
      key: "preferencias_noticias",
      title: "Noticias",
      question: "¿Qué noticias quieres recibir?",
      description: "",
      fields: [
        {
          key: "preferencias_noticias.frecuencia",
          path: ["preferencias_noticias", "frecuencia"],
          label: "Frecuencia",
          kind: "single",
          hint: "",
          options: [
            { id: "diario", label: "Diario" },
            { id: "semanal", label: "Semanal" },
          ],
          free_text_trigger: "",
          free_text_path: [],
          free_text_label: "",
        },
      ],
    },
    {
      key: "automatizaciones",
      title: "Automatizaciones",
      question: "¿Cuáles quieres activar?",
      description: "",
      fields: [
        {
          key: "automatizaciones.agenda",
          path: ["automatizaciones", "agenda"],
          label: "Agenda",
          kind: "toggle",
          hint: "Gestionar automáticamente correos de citas.",
          options: [],
          free_text_trigger: "",
          free_text_path: [],
          free_text_label: "",
        },
        {
          key: "automatizaciones.laboral",
          path: ["automatizaciones", "laboral"],
          label: "Laboral",
          kind: "toggle",
          hint: "Detectar ofertas relevantes.",
          options: [],
          free_text_trigger: "",
          free_text_path: [],
          free_text_label: "",
        },
      ],
    },
  ],
  required_sections: ["sector"],
};

const profile = (configuration: Record<string, unknown>) => ({
  id: PROFILE_ID,
  user_id: sampleUser.id,
  name: "Alex",
  description: "",
  configuration,
  is_primary: true,
  is_active: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
});

function renderPage(configuration: Record<string, unknown> = {}, extra = {}) {
  const stub = installFetchStub({
    "GET /api/profiles/catalog": { body: catalog },
    [`GET /api/profiles/${PROFILE_ID}`]: { body: profile(configuration) },
    "PATCH /api/profiles": { body: profile(configuration) },
    "GET /api/auth/me": { body: sampleUser },
    ...extra,
  });
  renderWithProviders(
    <Routes>
      <Route path="/profiles/:id/personalise" element={<PersonalisePage />} />
    </Routes>,
    { route: `/profiles/${PROFILE_ID}/personalise` },
  );
  return stub;
}

/** The body of the last PATCH the page sent. */
function lastPatch(calls: { url: string; init?: RequestInit }[]) {
  const patch = [...calls].reverse().find((c) => c.init?.method === "PATCH");
  expect(patch, "expected the page to save with PATCH").toBeTruthy();
  return JSON.parse(String(patch!.init?.body));
}

beforeEach(() => {
  setSession({
    access_token: "t",
    refresh_token: "r",
    expires_at: Date.now() + 30 * 60_000,
    user: sampleUser,
  });
});

describe("PersonalisePage — picking options", () => {
  it("selects an option by clicking it", async () => {
    renderPage();
    const chip = await screen.findByRole("checkbox", { name: /Ingeniería Informática/ });
    expect(chip).toHaveAttribute("aria-checked", "false");

    await userEvent.click(chip);
    expect(chip).toHaveAttribute("aria-checked", "true");
  });

  it("deselects an option by clicking it again", async () => {
    renderPage();
    const chip = await screen.findByRole("checkbox", { name: /Tecnología/ });
    await userEvent.click(chip);
    expect(chip).toHaveAttribute("aria-checked", "true");

    await userEvent.click(chip);
    expect(chip).toHaveAttribute("aria-checked", "false");
  });

  it("selects several options and counts them", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("checkbox", { name: /^Industria$/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /Tecnología/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /Inteligencia Artificial/ }));

    // the sector card reports its own count
    const sectorCard = screen.getByText("¿En qué sectores te interesa trabajar?").closest("div")!;
    expect(within(sectorCard.parentElement!).getByText("Seleccionadas: 3")).toBeInTheDocument();
  });

  it("a single-choice field keeps only one value", async () => {
    const { calls } = renderPage();
    await userEvent.click(await screen.findByRole("radio", { name: "Diario" }));
    await userEvent.click(screen.getByRole("radio", { name: "Semanal" }));
    await userEvent.click(screen.getByRole("checkbox", { name: /Tecnología/ }));
    await userEvent.click(screen.getAllByRole("button", { name: /guardar cambios/i })[0]);

    await waitFor(() => expect(calls.some((c) => c.init?.method === "PATCH")).toBe(true));
    expect(lastPatch(calls).configuration.preferencias_noticias.frecuencia).toBe("semanal");
  });

  it("reveals a text box only behind the 'Otra' option", async () => {
    renderPage();
    await screen.findByRole("checkbox", { name: /Otra/ });
    expect(screen.queryByLabelText("¿Cuál?")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("checkbox", { name: /Otra/ }));
    expect(await screen.findByLabelText("¿Cuál?")).toBeInTheDocument();
  });
});

describe("PersonalisePage — the generated JSON", () => {
  it("saves option ids, and never shows the user any JSON", async () => {
    const { calls } = renderPage();
    await userEvent.click(
      await screen.findByRole("checkbox", { name: /Ingeniería en Organización Industrial/ }),
    );
    await userEvent.click(screen.getByRole("checkbox", { name: /^Industria$/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: /Inteligencia Artificial/ }));

    // the JSON editor is not on screen until the user opens "Avanzado"
    expect(screen.queryByLabelText(/configuration/i)).not.toBeInTheDocument();

    await userEvent.click(screen.getAllByRole("button", { name: /guardar cambios/i })[0]);
    await waitFor(() => expect(calls.some((c) => c.init?.method === "PATCH")).toBe(true));

    expect(lastPatch(calls)).toEqual({
      configuration: {
        formacion: ["ingenieria_organizacion_industrial"],
        sector: ["industria_manufactura", "inteligencia_artificial"],
      },
    });
  });

  it("turns automations on and off as booleans", async () => {
    const { calls } = renderPage();
    const agenda = await screen.findByRole("switch", { name: "Agenda" });
    const laboral = screen.getByRole("switch", { name: "Laboral" });

    await userEvent.click(agenda);
    await userEvent.click(laboral);
    await userEvent.click(laboral); // back off again
    expect(agenda).toHaveAttribute("aria-checked", "true");
    expect(laboral).toHaveAttribute("aria-checked", "false");

    await userEvent.click(screen.getAllByRole("button", { name: /guardar cambios/i })[0]);
    await waitFor(() => expect(calls.some((c) => c.init?.method === "PATCH")).toBe(true));
    expect(lastPatch(calls).configuration.automatizaciones).toEqual({
      agenda: true,
      laboral: false,
    });
  });
});

describe("PersonalisePage — existing profiles", () => {
  it("loads a stored profile with its options already selected", async () => {
    renderPage({
      sector: ["tecnologia", "inteligencia_artificial"],
      automatizaciones: { agenda: true },
    });

    await waitFor(() =>
      expect(screen.getByRole("checkbox", { name: /Tecnología/ })).toHaveAttribute(
        "aria-checked",
        "true",
      ),
    );
    expect(screen.getByRole("checkbox", { name: /Inteligencia Artificial/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByRole("switch", { name: "Agenda" })).toHaveAttribute("aria-checked", "true");
    // untouched options stay off
    expect(screen.getByRole("switch", { name: "Laboral" })).toHaveAttribute("aria-checked", "false");
  });

  it("shows the human summary instead of the stored JSON", async () => {
    renderPage({ sector: ["tecnologia", "inteligencia_artificial"] });
    const summary = await screen.findByText("Tu perfil");
    const card = summary.closest("div")!.parentElement!;

    expect(within(card).getByText("Tecnología · Inteligencia Artificial")).toBeInTheDocument();
    expect(within(card).queryByText(/inteligencia_artificial/)).not.toBeInTheDocument();
  });

  it("keeps values an older profile stored that the catalogue does not know", async () => {
    const { calls } = renderPage({
      sector: ["tecnologia", "un_sector_antiguo"],
      notas_privadas: "no tocar",
    });

    // the unknown value is still shown as a chip, so it is not invisible
    const legacy = await screen.findByRole("checkbox", { name: /un_sector_antiguo/ });
    expect(legacy).toHaveAttribute("aria-checked", "true");

    await userEvent.click(screen.getByRole("checkbox", { name: /^Industria$/ }));
    await userEvent.click(screen.getAllByRole("button", { name: /guardar cambios/i })[0]);
    await waitFor(() => expect(calls.some((c) => c.init?.method === "PATCH")).toBe(true));

    const sent = lastPatch(calls).configuration;
    expect(sent.sector).toEqual(["tecnologia", "un_sector_antiguo", "industria_manufactura"]);
    expect(sent.notas_privadas).toBe("no tocar");
  });

  it("edits an existing profile without dropping the untouched sections", async () => {
    const { calls } = renderPage({
      formacion: ["ingenieria_informatica"],
      sector: ["tecnologia"],
    });
    await userEvent.click(await screen.findByRole("checkbox", { name: /^Industria$/ }));
    await userEvent.click(screen.getAllByRole("button", { name: /guardar cambios/i })[0]);
    await waitFor(() => expect(calls.some((c) => c.init?.method === "PATCH")).toBe(true));

    const sent = lastPatch(calls).configuration;
    expect(sent.formacion).toEqual(["ingenieria_informatica"]);
    expect(sent.sector).toEqual(["tecnologia", "industria_manufactura"]);
  });
});

describe("PersonalisePage — validation and progress", () => {
  it("cannot save an empty profile", async () => {
    renderPage();
    // wait for the sections to render, not just the header shell
    await screen.findByRole("progressbar", { name: /perfil completado/i });

    for (const save of screen.getAllByRole("button", { name: /guardado|guardar cambios/i })) {
      expect(save).toBeDisabled();
    }
    expect(screen.getByText(/selecciona al menos una opción/i)).toBeInTheDocument();
  });

  it("shows progress against the sections the backend grades", async () => {
    renderPage();
    const bar = await screen.findByRole("progressbar", { name: /perfil completado/i });
    expect(bar).toHaveAttribute("aria-valuenow", "0");

    await userEvent.click(screen.getByRole("checkbox", { name: /Tecnología/ }));
    await waitFor(() => expect(bar).toHaveAttribute("aria-valuenow", "100"));
  });

  it("keeps the JSON editor available but hidden under Advanced", async () => {
    renderPage({ sector: ["tecnologia"] });
    const advanced = await screen.findByRole("button", { name: /avanzado/i });
    expect(screen.queryByLabelText(/configuration/i)).not.toBeInTheDocument();

    await userEvent.click(advanced);
    expect(await screen.findByLabelText(/configuration/i)).toBeInTheDocument();
  });
});
