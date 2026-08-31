# Instalación

`DESCARGAR → EJECUTAR → INSTALACIÓN AUTOMÁTICA → READY`

El instalador detecta la plataforma, comprueba Docker, genera `.env`, ajusta
puertos, construye y levanta los servicios, importa los workflows, ejecuta
health checks reales y registra el arranque automático. Es **idempotente**
(re-ejecutar no duplica nada) y **reanudable** (guarda el estado).

## Plataformas soportadas

| | x64 | ARM64 |
|---|---|---|
| Windows | ✅ | ✅ |
| Linux (systemd o portable) | ✅ | ✅ |
| Raspberry Pi OS (64-bit) | — | ✅ |

No se soportan x86/32-bit ni ARM32/ARMv7.

## Requisito único

**Docker** (Docker Desktop en Windows/macOS; `docker` + `docker compose` v2 en
Linux). El instalador lo detecta; si en Linux tienes permisos de root puede
instalarlo con el script oficial. En Windows, si no está, te da el enlace y para.

## Windows

**Recomendado: `AutomationCenter-Setup.exe`** (instalador nativo Inno Setup).
Doble clic. Detecta y prepara WSL2 y Docker Desktop, despliega el stack,
ejecuta health checks y crea los accesos del menú Inicio. Detalle completo en
[docs/INSTALLATION.md](docs/INSTALLATION.md) y
[installer/windows/README.md](installer/windows/README.md).

Alternativa sin `.exe` (paquete portable):

1. Descomprime `automation-platform-<versión>-windows-<arch>.zip`.
2. **Doble clic en `AutomationPlatform-Setup.cmd`.**
3. Responde a las preguntas (claves de Gemini y Telegram — ver
   [CREDENCIALES.md](CREDENCIALES.md); puedes dejarlas en blanco y rellenarlas
   luego en `.env`).
4. Al terminar se abre el navegador en Automation Center (`localhost:3000`).

Modo desatendido (sin preguntas), tomando los secretos de un JSON:

```powershell
powershell -ExecutionPolicy Bypass -File installer\install.ps1 -Unattended -ConfigFile secrets.json
```

o de variables de entorno (`$env:GEMINI_API_KEY = "..."`, etc.).

Desinstalar:

```powershell
powershell -ExecutionPolicy Bypass -File installer\uninstall.ps1            # conserva los datos
powershell -ExecutionPolicy Bypass -File installer\uninstall.ps1 -PurgeData # borra todo
```

## Linux / Raspberry Pi

```sh
tar -xzf automation-platform-<versión>-linux-<arch>.tar.gz
cd automation-platform-<versión>-linux-<arch>
./installer/install.sh                 # interactivo
./installer/install.sh --unattended --config secrets.json
```

Con el paquete `.deb` (Debian/Ubuntu/Raspberry Pi OS):

```sh
sudo dpkg -i automation-platform-<versión>-<arch>.deb
sudo automation-platform-install
```

Desinstalar: `./installer/uninstall.sh [--purge-data]`

## Qué comprueba el health check

Los 6 contenedores (`pa-postgres`, `pa-n8n`, `pa-playwright`, `pa-profile`,
`pa-backend`, `pa-frontend`), HTTP de n8n (`/healthz`), del editor de perfil
(`/health`), del backend (`/api/health`) y del frontend, y que
`workflow_entity = 4`. Si algo falla, el instalador termina en `BLOCKED` y no
dice `READY`.

## Estado y logs

- Estado reanudable: `%LOCALAPPDATA%\AutomationPlatform\state.json`
  (Linux: `~/.local/share/automation-platform/state.json`)
- Log (sin secretos): `install.log` en el mismo directorio.

## Puertos

Por defecto n8n en `5678` y el editor de perfil en `7777`, solo en `127.0.0.1`.
Si están ocupados, el instalador elige otros y los guarda en `.env`.
Postgres **no se publica** al host.

## Arranque automático

- Windows: tarea programada `AutomationPlatform` (al iniciar sesión).
- Linux con systemd: servicio `automation-platform` (usuario o sistema).
- Sin systemd: añade `docker compose up -d` a tu arranque (cron `@reboot`).

## Generar los artefactos (build)

```powershell
powershell -File build\build.ps1                 # Windows: genera todos los zip/tar.gz
powershell -File build\build-exe.ps1             # Windows: AutomationCenter-Setup.exe (necesita Inno Setup 6)
```
```sh
./build/build.sh                                 # Linux/macOS
```

Salida en `dist/`: un archivo por plataforma + `.sha256` + `release-<versión>.json`,
y `AutomationCenter-Setup.exe`. El `.exe` firmado y el `.deb` se generan en CI
([.github/workflows/release.yml](.github/workflows/release.yml)) al empujar un
tag `vX.Y.Z`.
