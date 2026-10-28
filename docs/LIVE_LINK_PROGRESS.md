# Live Link — bitácora de implementación

**Rama:** `feature/live-editor-link`  
**PR:** [#2 — Add optional Live Link remote editor](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/pull/2)  
**Estado:** experimental, PR en borrador; no está listo para fusionar ni para generar APK.

## Objetivo acordado

Vincular el editor Godot 4.7.2 modificado que corre en Linux con el **editor Android real** del proyecto (LG K51, Android 11, 720×1600; ARM32 y ARM64). La meta es poder ver la pantalla del editor remoto e interactuar con él, y que los cambios hechos desde cualquiera de los extremos se reflejen en el otro. No debe ser una app sustituta ni un editor paralelo.

Live Link será una opción adicional del mismo Godot; no debe reemplazar ni romper GitHub Sync, Terreno 3D, ni las herramientas nativas existentes. No se debe generar un APK hasta consolidar y revisar los cambios.

## Decisión de arquitectura

- **Editor nativo:** la integración definitiva debe engancharse al proceso/editor Godot real. Un `EditorPlugin` de proyecto puede servir para prototipos, pero por sí solo no garantiza capturar toda la interfaz del editor Android ni controlar todos sus menús nativos.
- **Transporte:** WebSocket seguro (`wss://`) a través de un relay autenticado, con sala y roles de editor objetivo/controlador.
- **Seguridad:** token fuerte, validación de sala/rol, límites de tamaño/frecuencia y solo relay privado. No publicar un relay sin autenticación.
- **Sincronización:** la transmisión de pantalla y entrada remota no equivale a sincronizar archivos o estado interno del editor. La sincronización bidireccional de cambios de proyecto debe diseñarse y probarse por separado; GitHub Sync sigue siendo una herramienta independiente y unidireccional.
- **Compatibilidad:** conservar todos los controles normales de Godot. Los eventos sintetizados deben probarse con ratón, toque, teclado, menús, Inspector, diálogos y ventanas del editor; no asumir que todos responden igual.

## Implementación existente en la rama

El primer prototipo comprometido contiene:

- `scripts/live_link_addon/plugin.cfg` y `plugin.gd`: dock experimental para URL, sala, token y rol; envío de imagen comprimida y reenvío de eventos de entrada.
- `scripts/live_link_addon/README.md`: advertencias de límites y configuración.
- `relay/server.py`, `relay/requirements.txt`, `relay/Dockerfile`, `relay/render.yaml`: relay WebSocket con autenticación y plantilla de despliegue.
- PR #2 abierto como borrador para mantener aislado el trabajo de la rama principal.

**Importante:** estos archivos son una base experimental, no evidencia de que la conexión completa funcione en el editor Android.

## Bloqueo de integración actual

`scripts/apply_github_sync_patch.py` actualmente incrusta GitHub Sync y Terreno 3D en el código C++ del motor y los provisiona al abrir proyectos. Live Link todavía no está agregado a ese mecanismo. Por tanto, el addon no aparece garantizadamente como opción del Godot modificado y aún no hay integración global de captura/control.

Antes de modificar ese script, comprobar cada ancla exacta y la salida del generador. No activar ni sobrescribir archivos de proyectos existentes sin una política explícita y segura.

## Matriz de validación y aceptación

| Área | Criterio de aceptación | Estado |
|---|---|---|
| Documentación y aislamiento | Trabajo en rama separada, PR en borrador, sin APK | Hecho |
| Relay | Autenticación, separación de salas/roles, límites y rechazo de entradas inválidas | Hay pruebas del prototipo Linux separadas; repetirlas sobre la rama actual |
| Complemento GDScript | Parseo y carga con Godot 4.7.2 real, sin errores | Pendiente |
| Integración nativa C++ | Live Link accesible desde el editor modificado y sin regresiones en Sync/Terreno | Pendiente |
| Captura de pantalla | Captura útil del editor completo, incluidos paneles y menús relevantes | Pendiente; el framebuffer de la raíz puede ser incompleto |
| Control remoto | Toque/ratón, teclado, Inspector, menús, diálogos y selección funcionan | Pendiente |
| Conexión | Reconexión, desconexión, latencia y errores visibles en Output/Debugger | Pendiente |
| Sincronización de cambios | Definir y probar cómo se reflejan cambios de archivos y estado entre extremos, sin conflictos ni pérdida de datos | Pendiente |
| Android ARM32/ARM64 | Compilación y ejecución en ambos targets | Pendiente |
| LG K51 real | Pruebas de interfaz 720×1600, estabilidad, temperatura y rendimiento | Pendiente |
| No regresión | GitHub Sync y Terreno 3D siguen funcionando | Pendiente |
| APK | Solo tras superar las validaciones previas | No generado |

## Registro de trabajo

### 2026-10-28 — Revisión inicial y documentación

1. Recuperado el estado de la rama `feature/live-editor-link` y el PR #2.
2. Inspeccionado `scripts/apply_github_sync_patch.py`: confirma que hoy incrusta los addons de GitHub Sync y Terreno 3D, pero no Live Link.
3. Confirmado en el README del addon que la captura de la raíz del SceneTree puede no cubrir toda la interfaz y que los eventos sintetizados no garantizan el control de todas las superficies nativas.
4. Añadida esta bitácora para registrar decisiones, pruebas y bloqueos sin confundir código subido con una función terminada.

### 2026-10-28 — Primeros artefactos de prueba y diseño de sincronización

5. Añadido `tests/live_link/test_relay.py` con pruebas de integración para health, token incorrecto, rol duplicado, encaminamiento de pantalla y rechazo de coordenadas fuera de rango. **El archivo de pruebas está creado, pero aún no se ha ejecutado contra el relay de esta rama**; no contar como prueba superada.
6. Añadido `docs/LIVE_LINK_SYNC_PROTOCOL.md` con un diseño preliminar para sincronización de archivos bidireccional: hashes SHA-256, operaciones idempotentes, rutas seguras, transferencias por fragmentos, conflictos explícitos y borrados versionados.
7. La integración del addon en `scripts/apply_github_sync_patch.py) sigue pendiente. Se detectaron anclas sensibles al escape de tabulaciones en el código C++ embebido; no se guardó ninguna modificación parcial en ese archivo. No afirmar que Live Link ya se instala automáticamente.
8. No se ha desplegado el relay, ni se ha probado el addon GDScript en esta rama, ni se ha generado APK.

## Próximos pasos técnicos

1. Integrar Live Link en el generador de addons del motor con anclas comprobadas, sin cambiar el comportamiento de GitHub Sync ni Terreno 3D.
2. Ejecutar validación estática del parcheador y del contenido generado; verificar que los archivos incrustados coinciden con los addons fuente.
3. Validar sintaxis y carga del addon con Godot 4.7.2 y añadir pruebas automatizadas repetibles para el protocolo relay/control.
4. Diseñar la captura y entrada remota en la capa nativa del editor, ya que el addon por sí solo no satisface el objetivo completo.
5. Definir por separado el protocolo de sincronización de archivos/estado entre editores.
6. Solo después de las pruebas Linux, revisar compilación nativa y pruebas en Android ARM32/ARM64; reservar la prueba final de uso real para el LG K51.

No marcar una etapa como completada sin evidencia reproducible. No fusionar el PR ni generar APK mientras haya criterios pendientes.
