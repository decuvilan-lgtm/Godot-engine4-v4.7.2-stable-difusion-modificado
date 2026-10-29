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

## Estado de integración actual

Se modificó `scripts/apply_github_sync_patch.py` para que el generador incruste también `scripts/live_link_addon/plugin.gd` y `plugin.cfg` en el encabezado C++ generado, copie esos archivos al importar ZIP y complete los archivos ausentes al abrir un proyecto existente. El script agrega Live Link a la lista de plugins habilitados siguiendo el patrón que ya usa para GitHub Sync y Terreno 3D; en proyectos existentes no sobrescribe archivos de addon que ya existan.

**Límite importante:** el cambio está guardado en la rama, pero todavía no se ejecutó el parcheador contra el árbol real de código fuente Godot ni se compiló el C++. Por eso la integración debe considerarse implementada en el generador, no validada ni funcional todavía. Tampoco agrega aún captura/control en la capa nativa del editor: sigue siendo el complemento experimental.

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


### 2026-10-28 — Integración inicial en el generador

9. Actualizado `scripts/apply_github_sync_patch.py` (commit `53887f313ee0df000adf0f1cd63039394bc40805`) para incrustar el GDScript y el manifiesto de Live Link en el header generado y provisionarlo en importación ZIP/apertura de proyectos.
10. La ruta para proyectos existentes conserva los archivos de addon que ya existen; solo escribe los archivos de Live Link ausentes. La activación automática sigue el patrón previo de GitHub Sync/Terreno 3D.
11. **Pendiente de validar:** no se ha ejecutado este generador con `godot-source`, no se ha compilado el C++ modificado y no se han ejecutado las pruebas del relay de esta rama. No hay APK ni prueba Android.

### 2026-10-28 — Comprobación de regresión separada

12. Ejecutadas en `/tmp/godot-live-link-prototype` las pruebas `python3 tests/test_relay.py` y `GODOT_BIN=/tmp/godotlive/bin/Godot_v4.7.2-stable_linux.x86_64 python3 tests/test_godot_stream.py`: ambas terminaron con PASS; la segunda recibió un frame JPEG de 720×576 por el relay autenticado.
13. **Estas pruebas pertenecen al prototipo Linux separado, no a la rama GitHub `feature/live-editor-link`**, por lo que no validan el código recién integrado al generador ni sustituyen pruebas Android. Las cinco pruebas añadidas a `tests/live_link/test_relay.py` en la rama siguen pendientes de ejecución.

## Próximos pasos técnicos

1. Integrar Live Link en el generador de addons del motor con anclas comprobadas, sin cambiar el comportamiento de GitHub Sync ni Terreno 3D.
2. Ejecutar validación estática del parcheador y del contenido generado; verificar que los archivos incrustados coinciden con los addons fuente.
3. Validar sintaxis y carga del addon con Godot 4.7.2 y añadir pruebas automatizadas repetibles para el protocolo relay/control.
4. Diseñar la captura y entrada remota en la capa nativa del editor, ya que el addon por sí solo no satisface el objetivo completo.
5. Definir por separado el protocolo de sincronización de archivos/estado entre editores.
6. Solo después de las pruebas Linux, revisar compilación nativa y pruebas en Android ARM32/ARM64; reservar la prueba final de uso real para el LG K51.

No marcar una etapa como completada sin evidencia reproducible. No fusionar el PR ni generar APK mientras haya criterios pendientes.

### 2026-10-28 — Pruebas de relay y CI ampliada

14. Ejecutada la suite de relay en entorno local aislado: `python -m py_compile relay/server.py tests/live_link/test_relay.py` y `python -m unittest discover -s tests/live_link -v` → **5 pruebas OK**. El primer intento detectó un defecto en el fixture de pruebas (la aplicación aiohttp se reutilizaba entre bucles de eventos); se corrigió creando una aplicación nueva por prueba y se confirmó el pase.
15. Ampliada `scripts/validate_gdscript_load.py` para cargar también `scripts/live_link_addon` en Godot 4.7.2, y agregado al workflow de GitHub Actions el paso de pruebas del relay.
16. La ejecución CI `40754700090` terminó en `success` para el estado previo de la rama. La nueva ejecución disparada por los cambios de CI debe confirmar explícitamente el addon Live Link y las pruebas de relay.

17. La nueva CI detectó un error real de GDScript en Live Link: comparación entre `Vector2` y `Vector2i` al actualizar la textura del frame. Corregido en `scripts/live_link_addon/plugin.gd` convirtiendo el tamaño de imagen a `Vector2`. La suite de relay sí pasó en esa ejecución; queda esperar la nueva validación del parser Godot para confirmar el arreglo.

18. Confirmada la ejecución CI `40755224884`: **success**. Los cinco tests de relay pasaron y Godot 4.7.2 cargó los tres addons (GitHub Sync, Terreno 3D y Live Link) sin errores de GDScript ni recursos; también se procesaron las escenas fixture anidadas. La prueba detectó y permitió corregir el error `Vector2/Vector2i` de Live Link.
19. Añadidos checks de regresión para verificar que el header C++ generado contiene Live Link y que tanto importación ZIP como apertura de proyectos lo provisionan y habilitan. Esos nuevos checks están pendientes de la siguiente ejecución CI.
20. Sigue sin compilarse el C++ del motor ni probarse la app en Android. La carga del addon en el editor oficial Windows es una validación de GDScript, no prueba de control remoto real de la interfaz nativa.

21. Confirmada CI `40755615399`: **success**. Las seis pruebas del relay pasaron, incluida una nueva prueba positiva que verifica que el controlador puede enviar una entrada válida al editor objetivo y no recibe su propio evento.
22. Los checks de integración también pasaron: el header generado contiene los fuentes de Live Link, la importación ZIP lo instala, la apertura de proyectos existentes lo provisiona y ambas rutas lo habilitan. El editor oficial Godot 4.7.2 cargó los tres addons y escenas de prueba sin errores.
23. Estos resultados validan el generador, las rutas de instalación, la sintaxis/carga GDScript y el relay simulado en CI. **No validan** la compilación del motor C++, una conexión WSS desplegada, control de la interfaz nativa real ni el comportamiento en Android/LG K51. No se creó APK.

24. Revisión adicional del flujo de conexión: el nombre de sala predeterminado `godot-room-1` incluía guiones, pero el addon lo validaba con `is_valid_identifier()`, que podía rechazarlo antes de conectar. Alineada la validación del addon con el patrón permitido por el relay (`[A-Za-z0-9_.:-]{1,80}`). La CI se ejecutará de nuevo para validar esta corrección junto con los checks existentes.

25. Confirmada CI `40755946850`: **success** tras la corrección de validación de sala. La versión actual pasó los checks del generador/integración, las seis pruebas de relay y la carga de los tres addons en Godot 4.7.2.


### 2026-10-28 — Teclado remoto, aislamiento y estado de conexión

26. Confirmada CI `40757878782`: **success**. Las ocho pruebas del relay pasan, incluidas las regresiones que verifican el reenvío de teclas sin coordenadas de puntero y el aislamiento entre salas.
27. Corregido `scripts/live_link_addon/plugin.gd`: el complemento ahora rastrea explícitamente el intento de conexión y limpia `_connecting`, `_connected` y el mensaje de unión pendiente cuando el WebSocket termina cerrado tras un rechazo o una desconexión. El estado visible informa que la conexión se cerró o fue rechazada e indica revisar URL, token y sala antes de reintentar.
28. Confirmada CI `40758835812`: **success** para el cambio anterior. Pasaron los checks de integración del parcheador, las ocho pruebas del relay y la carga/parsing de los tres addons con Godot 4.7.2.
29. Límite: esto valida el estado de conexión del complemento y el protocolo relay en CI, no una sesión entre dos editores reales. La reconexión automática todavía no está implementada; el usuario debe pulsar «Conectar». La captura completa, el control de interfaz nativa, la sincronización de archivos, compilación C++ y las pruebas Android siguen pendientes.


### 2026-10-28 — Primer canal de operaciones de proyecto (transporte solamente)

30. Se añadió el documento `docs/CHATGPT_PROJECT_BRIDGE.md` para corregir el objetivo de producto: ChatGPT debe modificar archivos reales del proyecto seleccionado; pantalla/entrada remota no es el mecanismo principal.
31. El relay ahora admite un rol `agent` adicional y los mensajes `project_operation` (agent → target) y `project_result` (target → agent), conservando el flujo de pantalla/entrada anterior sin mezclar los tipos de mensaje.
32. El relay valida identificador de proyecto y operación, tipo de operación, rutas relativas, exclusión de `.git/` y `.godot/`, límites de tamaño, codificación Base64 y SHA-256 del contenido. El rol `target` no puede emitir operaciones y el rol `agent` no puede falsificar resultados.
33. Añadidos tests para validación de rutas/hash y encaminamiento agente→target→agente, más un workflow ligero `.github/workflows/validate-live-link-relay.yml` que ejecuta py_compile y la suite de relay al cambiar esos archivos.
34. **Límite explícito:** el relay solo transporta y valida el sobre del mensaje. Todavía no existe receptor de operaciones en el addon Godot, registro/selección de proyecto autorizada, cliente de herramientas conectado a ChatGPT, aplicación atómica/backups en el dispositivo ni prueba de extremo a extremo. No afirmar que ChatGPT puede modificar el proyecto Android todavía.
35. No se generó APK ni se fusionó el PR. La validación CI de los cambios recientes está pendiente de observarse en Actions.


### 2026-10-28 — Receptor experimental en el addon Godot

36. Añadido un ID persistente por proyecto en `ProjectSettings`, generado con bytes aleatorios, y mostrado en el dock para que el transporte pueda dirigir operaciones al proyecto correcto.
37. El addon ahora reconoce mensajes `project_operation` del rol `agent` y comprueba que el ID coincida con el proyecto abierto. Implementa las operaciones `create`, `update`, `rename` y `delete`, con validación de rutas relativas, bloqueo de `.git/` y `.godot/`, detección de enlaces simbólicos por las APIs de directorio, límites de contenido y verificación SHA-256.
38. Las modificaciones y eliminaciones respaldan primero la versión anterior en `user://live_link_backups/`; las escrituras se preparan en un temporal, se verifica el hash y se solicita un escaneo del FileSystem de Godot tras completar la operación. Los conflictos de versión base se rechazan sin sobrescritura.
39. Ampliado el workflow de validación para cargar el addon con el editor headless oficial Godot 4.7.2 además de ejecutar las pruebas del relay. **Este paso está pendiente de resultado en Actions para el receptor recién añadido.**
40. Sigue pendiente la prueba funcional de escritura/renombrado/borrado contra un proyecto temporal real y en Android. La carga GDScript, aunque pase, no demuestra el comportamiento del sistema de archivos Android ni la conexión con ChatGPT.


### 2026-10-28 — Identificación explícita antes de habilitar la conexión

41. El dock oculta el código hasta que el usuario pulsa «Revelar código identificador». Cada revelado desconectado genera un nuevo ID aleatorio de 128 bits y lo guarda en `ProjectSettings`; esto evita que copias de un proyecto conserven accidentalmente el mismo destino. Si ya hay una conexión activa o conectándose, el ID no puede rotarse.
42. «Copiar código» copia el ID al portapapeles. «Habilitar conexión (sin activarla)» y «Activar conexión» son pasos separados; el botón de activar comienza deshabilitado. Revelar/copiar no conecta ni concede permisos por sí solo.
43. Añadidos cinco checks de regresión de fuente para el bloqueo de activación, rotación aleatoria, separación entre revelar/copiar/conectar y no rotar durante una sesión. Son checks estáticos y no sustituyen pruebas de UI en Android.
44. CI anterior a esta última modificación: ejecución `40766730300` completada con éxito. La nueva lógica de generación/guardado y los nuevos checks necesitan su propia ejecución CI.
45. Sin APK, sin fusión del PR y sin afirmar prueba funcional en Android.

46. Endurecido el flujo de consentimiento: «Habilitar conexión» permanece deshabilitado tras revelar el código y solo se habilita cuando se pulsa «Copiar código». La acción de revelar no copia ni conecta automáticamente. El identificador no se puede regenerar mientras haya una conexión activa o en curso.
47. Añadidos checks estáticos para verificar que copiar el código es requisito para habilitar y que revelar/copiar/conectar son acciones separadas. La CI `40767603817` terminó en success para el complemento y la suite ejecutada; la prueba estática adicional agregada después debe confirmarse en una ejecución posterior.
48. Límite de cobertura: estos checks inspeccionan el contrato del código fuente. No simulan el portapapeles real, no ejecutan operaciones de archivos sobre un proyecto temporal y no sustituyen las pruebas en Android.


### 2026-10-28 — Continuidad de Live Link: cliente de agente, límites de red y aprobación

49. El cliente reutilizable de agente está en `relay/agent_client.py`; la guía está en `docs/LIVE_LINK_AGENT_CLIENT.md`. Verifica el sobre de política Android, el ID de proyecto, serializa operaciones y espera un resultado que coincida con el ID de operación y el ID de proyecto. Un timeout/desconexión deja el resultado desconocido: inspeccionar el proyecto antes de reintentar.
50. Se endureció la política de URL del complemento: `wss://` para hosts remotos; `ws://` solo para loopback o IP privada LAN válida, con comprobación de puerto/host. El cliente Python requiere `allow_insecure_lan=True` explícito para WS en IP privada. El relay escucha en `127.0.0.1` por defecto; usar `HOST=0.0.0.0` solo para una LAN confiable y limitar el puerto por firewall. WS en LAN no cifra el tráfico.
51. Las operaciones remotas de archivos ahora requieren confirmación explícita en el editor antes de aplicarse. Al aprobar, el receptor vuelve a validar identidad del proyecto y ruta antes de escribir. Revisar en el código las señales/ciclo de vida del diálogo y probar aprobación, rechazo, cambio de proyecto mientras el diálogo está abierto y cancelación; los checks de fuente no demuestran el comportamiento táctil real.
52. El relay fue corregido en el commit `0c2bdd62b43fb4c1895ad1883a84dca5b9483c9c` para que los resultados válidos `project_result` de una operación pendiente no se descarten por el limitador de frecuencia. Es importante conservar una prueba de regresión que envíe resultados consecutivos válidos y compruebe que ambos llegan al agente.
53. Las ejecuciones CI `40787657364` (“Validate Live Link project-operation relay”) y `40787657358` (“Source-only debug overlay checks”) terminaron en success para el commit `fe9733ced2d03ac2cacab8a28be30a7beb939b3d`. Validaron las pruebas de relay, sintaxis Python, aplicación limpia de parches, checks de GitHub Sync/Terreno 3D/overlay y carga de los tres addons con Godot 4.7.2. **Estas ejecuciones son anteriores a algunos cambios posteriores (incluido el ajuste de `project_result` del punto 52); no presentarlas como CI del HEAD actual.** Ejecutar/pollear Actions sobre el HEAD actual antes de afirmar que todo está validado.
54. El relay/cliente siguen siendo un transporte/agente, no una conexión nativa automática de ChatGPT. La app de ChatGPT no puede acceder por sí sola a `127.0.0.1` del teléfono ni a los archivos privados de Godot. Para funcionar sin API/PC/proveedor externo, el teléfono tendría que ejecutar también el modelo/agente capaz de producir operaciones; eso aún no está demostrado. No describir el sistema como peer-to-peer.
55. No se generó APK ni se fusionó el PR.

## Handoff para continuar en otro chat (estado al 2026-10-28)

**Repositorio:** `decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado`  
**Rama de trabajo:** `feature/live-editor-link`  
**PR:** [#2 — Add optional Live Link remote editor](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/pull/2) (mantener en borrador).  
**Bitácora:** este archivo, `docs/LIVE_LINK_PROGRESS.md`.  
**Guía de cliente/agente:** `docs/LIVE_LINK_AGENT_CLIENT.md`.  
**Documento de puente de proyecto:** `docs/CHATGPT_PROJECT_BRIDGE.md`.  
**Protocolo preliminar de sincronización:** `docs/LIVE_LINK_SYNC_PROTOCOL.md`.

### Objetivo que no debe perderse
Trabajar sobre el Godot Engine 4.7.2 Android real, no una app sustituta. Dispositivo objetivo: LG K51, Android 11, 720×1600; ARM32 y ARM64. Live Link debe coexistir con GitHub Sync, Terreno 3D y el editor normal. No compilar ni entregar APK hasta consolidar cambios, revisar regresiones y recibir aprobación de las pruebas.

### Qué existe hoy
- Addon experimental en `scripts/live_link_addon/plugin.gd` y `plugin.cfg`; prototipo de captura de imagen y eventos, estado de conexión y operaciones remotas de archivos.
- Generador `scripts/apply_github_sync_patch.py` provisiona/incrusta Live Link junto con los addons existentes; validar el resultado generado y la compilación C++ real, no confiar solo en checks de fuente.
- Relay WebSocket autenticado en `relay/server.py`, cliente de agente en `relay/agent_client.py`, política Android en `scripts/live_link_addon/android_capabilities.json`.
- Operaciones `create/update/rename/delete` con ID de proyecto y operación, hash/base hash, rutas relativas, exclusiones de `.git/` y `.godot/`, backups y consentimiento explícito en el editor.
- Reglas de URL: WSS remoto; WS solo loopback/LAN privada bajo restricciones. Relay loopback por defecto.
- Tests bajo `tests/live_link/`; documentación de límites sin API/proveedor y de la topología Android en `docs/LIVE_LINK_AGENT_CLIENT.md`.

### No está demostrado todavía
- Integración/captura/control de toda la interfaz nativa de Godot Android.
- Conexión real de dos editores y manejo fiable de toque, teclado, Inspector, menús y diálogos.
- Pruebas funcionales de aprobación/rechazo en el dispositivo, escritura/renombrado/borrado en un proyecto temporal Android, conflictos, backups y reconexión.
- Compilación C++ del motor y APK para ARM32 + ARM64.
- Ejecución en LG K51 y no regresión real de GitHub Sync/Terreno 3D.
- Integración automática con ChatGPT en la nube sin API: no está disponible por el simple hecho de tener el addon. Un agente/modelo que produzca operaciones sigue siendo necesario.

### Primeras tareas al abrir el siguiente chat
1. Leer esta bitácora y verificar el HEAD real de `feature/live-editor-link`; no asumir que `fe9733c` es el HEAD actual.
2. Revisar los commits posteriores a `fe9733c`, especialmente `0c2bdd62b43fb4c1895ad1883a84dca5b9483c9c`, y comprobar que los cambios de seguridad/aprobación están en la rama actual.
3. Ejecutar o disparar CI sobre el HEAD actual y esperar resultados; inspeccionar los logs si falla. No reportar el éxito de runs antiguos como validación del último commit.
4. Auditar las pruebas de consentimiento: aprobación, rechazo, cancelación, cambio de proyecto/ruta, symlinks, archivos existentes, conflicto de hash, rollback/backup y resultados consecutivos. Preferir pruebas funcionales automatizadas a regex/source-contract cuando sea viable.
5. Verificar el flujo del relay para resultados válidos consecutivos; ninguno debe perderse por rate limiting.
6. Revisar el generador y los artefactos generados; confirmar que no altera GitHub Sync/Terreno 3D. No construir APK todavía.
7. Registrar en esta bitácora cada commit, run ID, resultado y limitación comprobada.

### Reglas de trabajo para el siguiente chat
- No reiniciar el proyecto ni pedir al usuario que repita los requisitos documentados.
- No afirmar que una función está lista solo porque el código está subido o el parser pasa.
- Buscar fallos desde varios ángulos, esperar resultados de CI y diferenciar claramente pruebas estáticas, pruebas Linux, compilación C++ y pruebas Android reales.
- No generar APK ni fusionar el PR mientras existan criterios de aceptación pendientes.
- El usuario pidió que se le informe cuando la modificación esté completamente funcional, no con éxitos parciales como si fueran entrega final.



### 2026-10-28 — Auditoría funcional adicional y cobertura de resultados consecutivos

56. Revalidado el HEAD anterior a esta revisión mediante comparación con `fe9733ced2d03ac2cacab8a28be30a7beb939b3d`: la rama tenía un commit posterior centrado en documentación. Las ejecuciones `40787657364` (relay) y `40787657358` (overlay) corresponden a `fe9733c`, no deben presentarse como CI del nuevo HEAD.
57. Añadido `tests/live_link/test_consecutive_project_results.py` en el commit `de02e2c1b98d2b5b9931335db3a2e8a76ebad826`. Es una prueba funcional con WebSocket real de prueba y relay aiohttp: registra dos operaciones pendientes distintas, emite dos `project_result` válidos consecutivos sin pausa y exige que ambos lleguen al agente en orden, sin duplicados. La ejecución de CI de este commit aún no está confirmada por el conector; no marcarla como aprobada hasta observar Actions.
58. Hallazgo de auditoría en el receptor GDScript: `_apply_validated_operation` escribe un temporal, pero para actualizar un archivo existente elimina el original antes de renombrar el temporal. Si el proceso se interrumpe entre ambos pasos, el archivo principal puede quedar ausente aunque haya una copia de seguridad. Hay restauración de respaldo si el renombrado devuelve error, pero eso no cubre una terminación abrupta. Esto es un riesgo de atomicidad/recuperación pendiente de corregir y probar en un proyecto temporal; no declarar la protección de archivos completa.
59. La aprobación y el rechazo están implementados mediante `ConfirmationDialog`, y el receptor vuelve a comprobar identidad/ruta al aprobar. Las pruebas `test_project_identity_gate.py` siguen siendo principalmente contratos de fuente: no simulan de forma funcional los eventos del diálogo, el cambio de proyecto mientras está abierto, la cancelación ni las operaciones reales de sistema de archivos. La cobertura funcional de esas rutas sigue pendiente.
60. La comprobación de rutas inspecciona enlaces simbólicos en cada componente de la ruta antes de aplicar la operación; se debe añadir una prueba de ejecución que cubra enlaces normales y colgantes, destino de renombrado, directorios padres creados durante la operación y cambios concurrentes entre validación y escritura. La revisión de fuente no basta para cerrar esta superficie.
61. El generador `scripts/apply_github_sync_patch.py` contiene las rutas de instalación de GitHub Sync, Terreno 3D y Live Link en el mismo encabezado C++ generado y conserva los archivos existentes en la ruta de apertura de proyectos. Sigue sin demostrarse en esta sesión la ejecución del generador sobre un checkout real de `godot-source`, la compilación C++ resultante o una prueba de no regresión del editor. La presencia de los nombres en el generador no prueba por sí sola que el resultado compilado sea correcto.
62. No se ha generado APK, no se ha fusionado el PR y no hay evidencia de conexión directa con ChatGPT. El cliente de agente y el relay siguen siendo transporte; la conexión desde esta sesión de ChatGPT hasta el proyecto local Android continúa siendo un criterio bloqueante.


### 2026-10-28 — Resultados CI tras añadir la prueba funcional

63. CI `40791560717` (workflow “Validate Live Link project-operation relay”, run 121) terminó en **success** sobre el commit de prueba `de02e2c1b98d2b5b9931335db3a2e8a76ebad826`. El paso de sintaxis Python y la suite `python -m unittest discover -s tests/live_link -v` terminaron correctamente; el paso headless de Godot 4.7.2 también terminó en success. Esto confirma el relay y la prueba de resultados consecutivos en CI, además de la carga del addon en Godot oficial; no valida operaciones reales en Android ni conexión desde ChatGPT.
64. CI `40791560733` (workflow “Source-only debug overlay checks”, run 583) terminó con conclusión global **cancelled**, por lo que no se etiqueta como workflow aprobado. Sin embargo, todos los pasos de validación anteriores a la finalización aparecen como `success`, incluido el parcheo limpio de fuentes, GitHub Sync, Terreno 3D, compatibilidad combinada, suite de relay y carga de los tres addons en Godot 4.7.2; el estado global cancelado obliga a conservar la distinción y repetir esta ejecución si se necesita un check completo verde.
65. HEAD comprobado por comparación: `feature/live-editor-link` está tres commits por delante de `fe9733ced2d03ac2cacab8a28be30a7beb939b3d`; incluye la prueba funcional nueva y las actualizaciones de bitácora. No se ha iniciado compilación Android ni se ha generado APK.


### 2026-10-29 — Correcciones de relay, recuperación transaccional y CI de seguimiento

66. La corrección del relay ahora elimina un resultado pendiente expirado cuando llega el propio resultado, sin depender de que llegue otra operación para limpiar la sala. Se añadió `test_rejects_result_after_pending_operation_ttl`, que fuerza un TTL corto, espera la expiración y comprueba que el resultado tardío no llega al agente ni permanece en `PENDING`. La suite completa del relay pasó en CI `40792058791` (run 140) y `40792052887` (run 139), ambos sobre el commit `695f351e79bfba11317bfb2dd82425e673b82985`; el paso de parseo/carga del addon Godot 4.7.2 también terminó correctamente.
67. CI `40791968690` (run 136, commit `90ab2ca683059a4833cccdfbe2d301f9f4ea3443`) falló por una aserción de regresión demasiado amplia: buscaba la llamada de borrado del archivo que también es legítima en la operación `delete`. Se inspeccionó el log completo, se acotó la aserción al patrón antiguo de actualización que borraba el original antes de reemplazarlo y el run posterior `40791985291` terminó en success sobre `5d4ab25a85463e913db4f99d21552c493deaf88f`. El fallo no se ocultó ni se consideró un fallo del relay.
68. El reemplazo de archivos `update/create` ya no borra primero el original. Escribe y verifica el temporal, crea un journal por proyecto en `user://live_link_backups/<project_id>/active_transaction.json`, mueve el original a un rollback hermano y luego instala el temporal. Si la instalación falla intenta restaurar el original; al iniciar el addon, la recuperación lee solo el journal (no recorre todo el proyecto, para evitar bloquear proyectos grandes en móviles), valida que las rutas estén dentro del proyecto y que la copia de respaldo esté dentro del directorio de respaldo de ese proyecto, restaura o limpia temporales y elimina el journal cuando puede completar la recuperación.
69. La aprobación de operaciones `rename` ahora valida el destino antes de abrir el diálogo y muestra origen y destino al usuario. La aplicación vuelve a comprobar el destino al confirmar, para rechazar un destino que haya aparecido mientras el diálogo estaba abierto.
70. Se añadieron contratos de regresión para el journal/rollback y el destino de renombrado en `tests/live_link/test_project_identity_gate.py`. Estas comprobaciones son todavía de fuente, no una prueba de caída real del proceso ni de eventos de UI. El run `40791968690` identificó una aserción defectuosa; el run `40791985291` pasó la suite completa de 42 pruebas, incluyendo resultados consecutivos, expiración de resultados, aprobación y contratos de recuperación, y cargó el addon con Godot 4.7.2. Los commits posteriores añadieron validación adicional de rutas del journal; CI `40792058791` / `40792052887` verificó el commit `695f351e79bfba11317bfb2dd82425e673b82985`.
71. CI de fuente combinada `40791985296` (commit `5d4ab25a85463e913db4f99d21552c493deaf88f`) y la ejecución de fuente combinada `40792058808` (commit `695f351e79bfba11317bfb2dd82425e673b82985`) requieren revisar su conclusión final antes de usarla como check completo. No usar los resultados de un commit anterior como prueba de los cambios nuevos.
72. HEAD de trabajo al escribir esta entrada: `695f351e79bfba11317bfb2dd82425e673b82985`; comparación con `fe9733ced2d03ac2cacab8a28be30a7beb939b3d` muestra cuatro o más commits posteriores (los documentos pueden sumar commits adicionales). PR #2 continúa abierto en borrador. Sin APK, sin merge y sin prueba de conexión directa con ChatGPT. Siguen bloqueantes las pruebas reales de operaciones en filesystem, recuperación por interrupción, symlinks y cambios concurrentes, el check combinado completamente verde, el generador/artefactos compilados y el editor Android ARM32/ARM64.


### 2026-10-29 — Revalidación de conflictos y último estado observado

73. Se reforzaron las comprobaciones inmediatamente antes de mutar archivos: `delete` vuelve a comparar el SHA-256 después de crear el respaldo; `rename` vuelve a comprobar hash del origen y que el destino siga libre; `update` vuelve a comprobar que el archivo conserve el hash base; `create` vuelve a rechazar si apareció un archivo/directorio después de la comprobación inicial. Esto reduce la ventana de carrera, pero no elimina por completo los cambios concurrentes del sistema de archivos entre la última comprobación y la operación nativa.
74. Se amplió `test_project_identity_gate.py` para comprobar que el journal limite el origen, el rollback, el temporal y la copia de seguridad a sus raíces permitidas, y que delete/rename/update repitan la comprobación del hash después del respaldo. Continúa siendo una prueba de contrato de fuente; no simula una modificación concurrente real en el filesystem.
75. CI `40792309525` (run 147, commit `848da95ad1876a7a3da5ea03682e0d6294a38adc`) terminó en **success**: sintaxis Python, las 43 pruebas de la suite `tests/live_link` y carga del addon Live Link en Godot 4.7.2. El log confirma que el editor headless inicializó y cargó `res://addons/live_link/plugin.gd`; las advertencias de clases editoriales “not exposed” del registro son mensajes del escaneo de clases del editor y no hicieron fallar el paso.
76. La ejecución combinada de fuentes `40792310630` (run 598, commit `848da95ad1876a7a3da5ea03682e0d6294a38adc`) seguía en estado `pending` al consultar Actions. La ejecución anterior `40791985296` seguía marcada `in_progress` sin jobs devueltos por la API; no debe interpretarse como resultado satisfactorio. Por tanto, la validación del generador y la compatibilidad combinada para el código más reciente siguen pendientes de confirmación de CI.
77. Se revisó `scripts/apply_github_sync_patch.py`: el generador incrusta los archivos de GitHub Sync, Terreno 3D y Live Link en el encabezado C++ generado; las rutas de instalación para ZIP y apertura de proyectos están presentes. Esto sigue siendo revisión de código y no sustituye la ejecución satisfactoria del workflow de fuentes, la compilación C++ ni pruebas funcionales del editor.
78. HEAD de código validado por el workflow Live Link: `848da95ad1876a7a3da5ea03682e0d6294a38adc`. Después se actualizará esta bitácora sin alterar el código probado. PR #2 sigue abierto y en borrador. No APK ni merge. Los criterios de aprobación/rechazo mediante UI real, recuperación tras terminar el proceso, symlinks y carreras reales, ejecución/compilación del generador y pruebas en Android ARM32/ARM64 siguen sin cerrarse; la conexión automática directa con ChatGPT no está demostrada.


### 2026-10-29 — Confirmación final de la suite Live Link para el último código

79. CI `40792444637` (run 149) terminó en **success** sobre `6c4aaa3f0ebdcc9cfb342e1a79afcd85ebd6c7b0`. Los logs completos confirman que se ejecutaron **44 pruebas** de `tests/live_link` y terminaron en `OK`; también se completó el parseo/carga del addon con Godot 4.7.2. El nuevo test comprueba que la recuperación por journal se invoca al iniciar el addon. La ejecución de relay incluye las pruebas funcionales WebSocket para resultados consecutivos y resultados caducados.
80. La validación combinada del generador/artefactos `40792449842` (run 600, mismo commit) permanecía `pending` sin jobs asignados al último chequeo. Las ejecuciones de fuente anteriores se cancelaron al llegar commits nuevos antes de iniciar sus jobs. No se etiqueta como aprobada; queda pendiente un run combinado verde para el código actual.
81. El commit `848da95ad1876a7a3da5ea03682e0d6294a38adc` contiene los cambios de revalidación de hashes y pruebas de carrera; `6c4aaa3f0ebdcc9cfb342e1a79afcd85ebd6c7b0` añade la comprobación de que la recuperación está conectada al inicio. Esta actualización es solo documental y no modifica el código validado por CI run 149.
82. No se ha ejecutado una prueba de fallo abrupto real del proceso Godot, ni pruebas automatizadas que manipulen el diálogo de aprobación/rechazo, ni pruebas de filesystem con symlinks/cambios concurrentes reales. El parseo y las pruebas de contrato no demuestran esas propiedades de extremo a extremo. Tampoco se ha compilado C++ del generador ni probado el editor Android en ARM32/ARM64. Live Link continúa experimental y no se ha demostrado una conexión automática desde ChatGPT a Godot.


### 2026-10-29 — Auditoría técnica, contrato de operación y límites reales

83. En `scripts/live_link_addon/plugin.gd` se añadió validación del sobre de operación **antes** de abrir el diálogo: ID de operación con formato permitido, SHA-256 base válido para `update`/`rename`/`delete`, ausencia de hash base para `create`, y formato/tamaño de contenido y SHA-256 declarada para `create`/`update`. El commit de código es `08ccb5d0b7c26b7358662aab7fbbbe298ef9642e`; `616cedd56d0d4853a91f0c17740e2ca8f415e614` añade el test de contrato correspondiente.
84. La ejecución [40794212632](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/40794212632) terminó en **success** sobre el commit `616cedd56d0d4853a91f0c17740e2ca8f415e614`: 47 pruebas Python pasaron y Godot 4.7.2 headless cargó el complemento sin errores de script/recursos. La ejecución [40794293143](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/40794293143) también terminó en success en `9ca1c55dc51b965280586d207ddf61f838e996e3`, que añade documentación y conserva el mismo código validado.
85. Se actualizó `scripts/live_link_addon/README.md` para evitar afirmar que la detección de enlaces simbólicos está garantizada en Android. La documentación de Godot 4.7 enumera `DirAccess.is_link()` como implementado en macOS, Linux y Windows, pero no Android; por tanto, el guard actual no basta para garantizar resistencia a symlinks en el dispositivo objetivo.
86. Se creó `docs/LIVE_LINK_TECHNICAL_AUDIT.md` con la arquitectura, resultados de CI, referencias oficiales y un plan por fases. La documentación de Godot también aclara que `Input.parse_input_event()` alimenta eventos al motor y no mueve el cursor del sistema operativo ni cambia ventanas del sistema; controlar todos los paneles/diálogos del editor Android debe probarse en el dispositivo y podría requerir integración nativa.
87. El puente ChatGPT→Godot sigue sin implementarse. El relay y el cliente agente son componentes de transporte, no un conector MCP de ChatGPT. La documentación actual de OpenAI indica que los servidores MCP personalizados se conectan desde la web, no directamente desde la app móvil; la disponibilidad de escritura depende del plan. Se documentó la ruta sin API de modelos (ChatGPT invocando un MCP remoto) y el flujo alternativo actual GitHub→Godot Sync. No se debe presentar como conexión funcional hasta que haya puente y prueba de extremo a extremo.
88. HEAD documental actual: `bca7e11f22d5b02d9d648d946c993a376af22e5c`. Los cambios de documentación no modifican la lógica probada. PR #2 continúa abierto en borrador. Sin APK, sin merge y sin prueba física Android. Bloqueantes: harness de filesystem real en Godot, simulación de interrupciones, UI de aprobación/rechazo en dispositivo, captura/entrada remota en Android, protección de rutas apropiada para Android y disponibilidad real del puente MCP.
