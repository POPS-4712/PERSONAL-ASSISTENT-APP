# Credenciales y APIs — guía completa

Todas las automatizaciones funcionan **sin tocar código**. Solo hay que dar de
alta estas credenciales. Ordenadas de menos a más esfuerzo.

| Servicio | Lo usan | Dónde se pone | Coste |
|---|---|---|---|
| Gemini (Google AI Studio) | Noticias, Marca Personal, Laboral, Email | `.env` | Gratis (cuota generosa) |
| Telegram Bot | Noticias, Marca Personal, Laboral, Email | `.env` | Gratis |
| Google OAuth (Gmail + Calendar) | **solo** Email | n8n → Credentials | Gratis |

Nada de esto se sube a git: `.env` está en `.gitignore`.

---

## 1. Gemini — `GEMINI_API_KEY`

1. Entra en <https://aistudio.google.com/app/apikey> con tu cuenta Google.
2. **Create API key** → cópiala.
3. En `.env`:
   ```
   GEMINI_API_KEY=AIza...
   GEMINI_MODEL=gemini-2.5-flash
   ```
4. Aplica: `docker compose up -d`

Probar que va (desde la carpeta del proyecto):
```bash
curl -s -H "x-goog-api-key: TU_KEY" -H "Content-Type: application/json" \
  -d "{\"contents\":[{\"parts\":[{\"text\":\"di hola\"}]}]}" \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
```
Respuesta con `"candidates"` = OK.

---

## 2. Telegram — `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`

1. En Telegram, habla con **@BotFather** → `/newbot` → nombre y usuario del bot.
   Te da un token tipo `8123456:AAE...`. Ese es `TELEGRAM_BOT_TOKEN`.
2. **Escribe cualquier mensaje a tu bot** (búscalo por su @usuario y pulsa Start).
3. Abre en el navegador (pon tu token):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Busca `"chat":{"id":123456789,...}`. Ese número es `TELEGRAM_CHAT_ID`.
4. En `.env`:
   ```
   TELEGRAM_BOT_TOKEN=8123456:AAE...
   TELEGRAM_CHAT_ID=123456789
   ```
5. Aplica: `docker compose up -d`

Probar:
```bash
curl -s "https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHAT_ID>&text=hola"
```
Debe llegarte "hola" al chat.

---

## 3. Google OAuth (Gmail + Calendar) — solo para el workflow **Email**

Este es el único que necesita OAuth. Los workflows de Noticias, Marca Personal y
Laboral **no lo necesitan**.

### 3.1 Crear las credenciales en Google Cloud

1. <https://console.cloud.google.com/> → crea un proyecto (p. ej. "asistente-tdr").
2. **APIs y servicios → Biblioteca**: activa **Gmail API** y **Google Calendar API**.
3. **APIs y servicios → Pantalla de consentimiento OAuth**:
   - Tipo: **Externo**.
   - Rellena nombre de la app y tu correo.
   - **Usuarios de prueba**: añade tu propia dirección Gmail. (Con la app en modo
     "Testing" no necesitas verificación de Google.)
4. **Credenciales → Crear credenciales → ID de cliente de OAuth**:
   - Tipo: **Aplicación web**.
   - **URI de redirección autorizados**: aquí va la que te dé n8n en el paso
     siguiente, normalmente:
     `http://localhost:5678/rest/oauth2-credential/callback`
   - Copia el **Client ID** y el **Client secret**.

### 3.2 Darlas de alta en n8n

1. Abre <http://localhost:5678> → **Credentials → New**.
2. Crea una credencial **"Google Calendar OAuth2 API"**:
   - Pega Client ID y Client secret.
   - n8n muestra la **OAuth Redirect URL** exacta → cópiala y pégala en Google
     Cloud (paso 3.1.4) si no coincide.
   - Pulsa **Connect / Sign in with Google** y acepta los permisos.
3. Crea otra credencial **"Gmail OAuth2"** igual (puedes reutilizar el mismo
   Client ID/secret).
4. Abre el workflow **«Asistente - Email»**:
   - Nodo **Gmail - Correo nuevo** → selecciona la credencial Gmail.
   - Nodo **Google Calendar - Crear evento** → selecciona la credencial Calendar
     y confirma que `Calendar = primary`.
5. Pulsa **Execute workflow** para probar con los últimos correos no leídos.
6. Si va bien, **activa** el workflow.

> Alcances (scopes) que pedirá: lectura de Gmail y gestión de eventos de
> Calendar. Puedes revocarlos cuando quieras en
> <https://myaccount.google.com/permissions>.

---

## Scraper de empleo (workflow Laboral) — nota

El workflow Laboral usa el servicio `playwright` incluido, que hace scraping de
las **páginas públicas de LinkedIn** (sin login). Si LinkedIn bloquea el acceso
anónimo, cae automáticamente a la API pública de **arbeitnow.com** para no
quedarse sin datos.

Para scraping fiable de LinkedIn con tu sesión iniciada (cookies) o de InfoJobs,
esa parte se añade más adelante; no requiere cambios en los workflows, solo en el
servicio `playwright/`.

---

## Checklist rápida

- [ ] `.env` con `GEMINI_API_KEY` real
- [ ] `.env` con `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` reales
- [ ] `docker compose up -d` tras editar `.env`
- [ ] Workflow **Noticias** probado → llega a Telegram → activado
- [ ] Workflow **Marca Personal** probado → borradores en `output/marca-personal/` → activado
- [ ] Workflow **Laboral** probado → ofertas a Telegram → activado
- [ ] (opcional) Google OAuth para **Email** → probado → activado
