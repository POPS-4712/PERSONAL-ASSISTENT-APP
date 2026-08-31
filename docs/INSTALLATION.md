# Instalación de Automation Center

`DESCARGAR → EJECUTAR → INSTALACIÓN AUTOMÁTICA → LOGIN → DASHBOARD`

## Arquitectura

```
WEB (Vercel)                         LOCAL (este instalador)
Browser → Vercel → Backend remoto    Browser → localhost:3000 → Backend local
                → PostgreSQL/n8n              → Docker (postgres, n8n,
                                                playwright, backend, frontend)
```

El instalador Windows despliega la parte **LOCAL**. El frontend en Vercel es
independiente y no se toca aquí.

## Plataformas soportadas

|         | x64 | ARM64 |
|---------|-----|-------|
| Windows 10 (2004+) / 11 | ✅ | ✅ |
| Linux (systemd o portable) | ✅ | ✅ |
| Raspberry Pi OS 64-bit | — | ✅ |

No se soporta x86/32-bit ni ARM32/ARMv7.

## Windows — con `AutomationCenter-Setup.exe`

1. Descarga `AutomationCenter-Setup.exe` (de la [release](../.github/workflows/release.yml)).
2. Doble clic. El asistente:
   - comprueba Windows, arquitectura, RAM y disco;
   - **WSL2**: si falta, habilita `Microsoft-Windows-Subsystem-Linux` y
     `VirtualMachinePlatform`, fija WSL v2 e instala Ubuntu. Si Windows pide
     reiniciar, lo detecta y **continúa solo tras el reinicio** (RunOnce);
   - **Docker Desktop**: si falta, lo instala (winget o instalador oficial),
     lo arranca y espera a `docker info` + `docker compose`. Si ya está, lo
     reutiliza (no toca tus contenedores);
   - genera `.env` con secretos criptográficos;
   - `docker compose build` + `up`;
   - crea la BD `automation_center` (si no existe — nunca `DROP`);
   - aplica migraciones (`alembic upgrade head`, en el arranque del backend);
   - importa los 4 workflows (upsert por id: no duplica);
   - health checks reales de los 6 contenedores + HTTP de backend/frontend/n8n;
   - registra el arranque automático y (opcional) el icono de bandeja.
3. Al terminar abre `http://localhost:3000`. Crea la cuenta (**el primer
   usuario es admin**) y conecta credenciales.

### Desatendido

```powershell
AutomationCenter-Setup.exe /VERYSILENT /SUPPRESSMSGBOXES
```

Los secretos externos (Gemini, Telegram) se rellenan luego en `.env` o desde
el panel. Con `installer\install.ps1 -Unattended -ConfigFile secrets.json`
se pueden inyectar en la instalación.

## Windows / Linux — paquete portable

```powershell
# Windows: doble clic en AutomationPlatform-Setup.cmd  (o)
powershell -ExecutionPolicy Bypass -File installer\install.ps1
```
```sh
./installer/install.sh                       # Linux / Raspberry Pi
sudo dpkg -i automation-platform-<v>-<arch>.deb && sudo automation-platform-install
```

## Requisitos que gestiona el instalador

| Dependencia | Si ya está | Si falta (Windows) |
|---|---|---|
| WSL2 + distro Linux | se reutiliza | se habilita/instala (puede requerir 1 reinicio) |
| Docker Desktop | se reutiliza (versión + `docker info`) | se instala en silencio |
| Docker Compose v2 | se comprueba | viene con Docker Desktop |
| PostgreSQL, n8n, Playwright, Backend, Frontend | contenedores del `docker-compose.yml` | los levanta el instalador |

## URLs (todo en `127.0.0.1`)

| URL | Servicio |
|---|---|
| http://localhost:3000 | **Automation Center** (panel) |
| http://localhost:8080/api/health | API (backend) |
| http://localhost:5678 | n8n (workflows) |
| http://localhost:7777 | editor de perfil |

Si un puerto está ocupado, el instalador elige otro y lo guarda en `.env`.

## Gestión (sin PowerShell)

Menú Inicio → **Automation Center**:

- **Automation Center** — abre el panel
- **Iniciar / Parar / Reiniciar / Estado**
- **Ver logs**
- **Copia de seguridad**
- **Volver a ejecutar la instalación**
- **Desinstalar**

Icono de bandeja (si lo activaste): mismo menú + estado ● Running/Stopped.

## Estado y logs

- Estado reanudable: `%LOCALAPPDATA%\AutomationPlatform\state.json`
- Log (sin secretos): `%LOCALAPPDATA%\AutomationPlatform\install.log`
- Log del `.exe`: pásale `/LOG="C:\ruta\setup.log"`

## Troubleshooting

| Síntoma | Causa / solución |
|---|---|
| "Docker Desktop is installed but not running" | Abre Docker Desktop, espera a que diga *Running*, reintenta. |
| Se queda en "esperando al motor de Docker" | Primer arranque de Docker tras instalar: puede tardar 1–2 min; a veces hace falta cerrar sesión y volver a entrar (grupo `docker-users`). |
| "REINICIO NECESARIO" | Reinicia; la instalación continúa sola al iniciar sesión. |
| Un contenedor no llega a `healthy` | `docker compose logs <servicio>` desde la carpeta de instalación, o menú → Ver logs. |
| `workflow_entity ≠ 4` | Revisa `docker compose logs n8n`. Los 4 IDs esperados: `0ikHqQCWMke67aoI`, `pa01email000001`, `pa02laboral00001`, `pa04marcapersonal`. |
| Puerto ocupado | El instalador remapea y lo anota en `.env`; mira la línea `n8n:… backend:…` del log. |
| El panel no abre | `http://localhost:3000` — comprueba `pa-frontend` en el menú → Estado. |

Detalle de actualización y backup: [UPGRADE.md](UPGRADE.md) ·
[BACKUP-RESTORE.md](BACKUP-RESTORE.md).
