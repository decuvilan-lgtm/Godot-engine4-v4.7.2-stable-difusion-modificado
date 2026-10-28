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
