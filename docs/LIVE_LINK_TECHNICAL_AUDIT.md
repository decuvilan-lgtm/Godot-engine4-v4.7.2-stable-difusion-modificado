# Live Link — auditoría técnica y ruta hacia funcionamiento real

Fecha de revisión: 2026-10-28/29  
Rama revisada: `feature/live-editor-link`

## Resumen ejecutivo

Live Link ya tiene tres piezas separadas: un complemento dentro del editor Godot, un relay WebSocket autenticado y un cliente Python de agente. La ruta de operaciones admite `create`, `update`, `rename` y `delete`; el editor valida el proyecto destino, pide aprobación explícita, compara SHA-256 para detectar conflictos y mantiene copias de seguridad.

Esto todavía **no equivale a una integración ChatGPT→Godot terminada**. Ya se añadió una prueba de integración de filesystem que ejecuta operaciones reales dentro de Godot 4.7.2 headless; faltan simulación de cierre abrupto del proceso, pruebas del diálogo de aprobación, entrada/captura en Android físico y el puente de herramientas compatible con ChatGPT.

## Estado verificado en CI

La ejecución [40794825337](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/40794825337) terminó en **success** en el commit `d42d847e119e1ea77372643437074ba62ff510a2`. Corrieron 47 pruebas Python y la carga de Godot 4.7.2 headless ejecutó además `LIVE_LINK_FS_TESTS_PASSED` sin errores, errores de parseo ni fugas ObjectDB.

La validación combinada [40794936417](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/actions/runs/40794936417) terminó en **success** en el commit `87ac82d342fec604ec8f23f4447c1e27a21733f7`. Pasaron la aplicación del parche a un upstream limpio, la integración de GitHub Sync, Terrain 3D, el parche de arranque Android, las regresiones combinadas, la descarga del editor oficial Windows Godot 4.7.2, las 47 pruebas Live Link y la carga de los tres complementos con escenas anidadas. Esto valida el generador y la compatibilidad de fuentes en CI, pero no equivale a compilar el editor Android ARM32/ARM64 ni probar el teléfono.

El harness `tests/live_link/godot_filesystem_harness/godot_filesystem_harness.gd` opera sobre archivos reales del proyecto temporal de Godot: creación normal, creación de archivo vacío, actualización, conflicto por SHA-256 obsoleto, renombrado, eliminación, recuperación tras mover el original a rollback y recuperación tras instalar el reemplazo pero antes de limpiar rollback/temporal. Durante la prueba se detectó y corrigió un defecto real: `HashingContext.update()` rechaza un buffer vacío; `_sha256_bytes()` ahora finaliza directamente el contexto inicializado para obtener el hash SHA-256 correcto del archivo vacío.

Estas pruebas son mucho más fuertes que las comprobaciones estáticas, pero **no** simulan matar el proceso Godot en cada instrucción ni prueban el teléfono LG K51, el diálogo de aprobación/rechazo, la captura completa de pantalla o la entrada global del editor Android.

## Arquitectura necesaria

1. **Godot Android:** el complemento Live Link identifica el proyecto y recibe operaciones. No debe ejecutar comandos arbitrarios ni aplicar cambios sin la confirmación visible del usuario.
2. **Relay:** autentica conexiones y transporta pantalla, eventos y resultados. El servidor de desarrollo no debe exponerse directamente a Internet; el acceso remoto requiere TLS/WSS, token fuerte y secretos fuera del repositorio.
3. **Agente:** `relay/agent_client.py` envía una operación y espera una respuesta explícita del editor. Que el relay haya recibido un mensaje no significa que el archivo haya cambiado.
4. **Puente de ChatGPT:** para que ChatGPT invoque herramientas de forma directa hace falta un servidor MCP remoto que exponga herramientas limitadas y llame al cliente agente. El cliente Python actual no es por sí mismo una herramienta conectada a ChatGPT.

Una integración MCP no necesita llamar a la API de modelos de OpenAI si ChatGPT invoca las herramientas del conector, pero requiere que la cuenta y la interfaz de ChatGPT admitan ese tipo de conexión y acciones de escritura. La documentación actual indica que las conexiones MCP personalizadas son solo para la web, que ChatGPT no conecta directamente con un servidor MCP local y que la disponibilidad de escritura depende del plan. Verifica las condiciones vigentes antes de invertir en desplegar el puente.

Mientras ese puente no esté disponible, el flujo viable desde el ChatGPT actual es: editar el repositorio con la conexión GitHub, revisar los cambios y sincronizarlos desde el editor Android. Eso no es control en vivo de la UI.

## Hallazgos técnicos que afectan la fiabilidad

### 1. Compatibilidad de Android

El editor Android de Godot sigue teniendo limitaciones específicas y la documentación lo trata como una plataforma experimental/en evolución. Hay que probar cada API de editor y de archivos en el editor Android real, no asumir que una prueba headless de Linux equivale a Android.

La documentación de Godot 4.7 dice que `DirAccess.is_link()` está implementado en macOS, Linux y Windows; Android no aparece en esa lista. Por ello, las comprobaciones actuales de enlaces simbólicos **no deben considerarse una garantía de seguridad en Android**. Antes de afirmar protección completa frente a enlaces simbólicos, se necesita una comprobación nativa Android compatible con no-follow/canonicalización o una restricción de almacenamiento validada en el dispositivo.

### 2. Entrada remota

`Input.parse_input_event()` permite alimentar eventos al motor, pero la documentación advierte que no mueve el cursor del sistema operativo ni cambia entre ventanas del sistema. Por eso no puede darse por probado que el complemento controle todos los menús, paneles, diálogos nativos o ventanas del editor Android. Es necesaria una prueba táctil en el teléfono y, si no alcanza, un punto de integración nativo con el editor.

### 3. Transacciones de archivos

El diario y los archivos temporales/rollback reducen el riesgo de perder el original, y las revalidaciones SHA-256 detectan cambios concurrentes en ventanas conocidas. El harness ya comprueba operaciones reales y dos estados de recuperación (antes de instalar y después de instalar el reemplazo). No elimina por completo las carreras TOCTOU ni sustituye una terminación abrupta del proceso en cada punto de la transacción; esa simulación sigue pendiente.

### 4. Seguridad del relay

- WSS/TLS para cualquier conexión remota; `ws://` solo para loopback o una LAN privada de confianza.
- Token aleatorio fuerte almacenado como variable de entorno/secret, nunca en el repositorio ni en los logs.
- Validación en el relay y nuevamente en el editor: proyecto, operación, rutas, tamaño, hashes, rol y resultado.
- Mantener aprobación visible en Godot y confirmar el resultado de la operación antes de darla por terminada.
- Añadir límites operativos para conexiones/salas si el relay se despliega públicamente, y registrar eventos de seguridad sin guardar tokens ni contenido sensible.
- No habilitar ejecución de shell, scripts arbitrarios ni acceso de escritura fuera de la raíz del proyecto.

## Plan de trabajo recomendado

### P0 — contrato y validación (en curso)
- [x] ID de proyecto y activación explícita de conexión.
- [x] Operaciones del relay limitadas por rol, tamaño, ruta, SHA-256 y política `android_editor`.
- [x] Respuesta de resultado ligada al proyecto y a la operación pendiente.
- [x] Rechazo de resultados tardíos y de IDs de operación repetidos durante la ventana de protección.
- [x] Validación adicional de ID de operación, huellas y tamaño de contenido antes de pedir aprobación.
- [ ] Revisión final de estados de error y respuesta clara cuando el proyecto objetivo no coincide.

### P1 — pruebas reales del receptor
- [x] Crear un harness que ejercite operaciones reales sobre el filesystem en Godot 4.7.2 headless.
- [x] Probar creación normal, archivo vacío, actualización, conflicto por SHA-256 obsoleto, renombrado y eliminación.
- [x] Comprobar recuperación tras mover el original a rollback y tras instalar el reemplazo antes de limpiar temporales.
- [ ] Simular terminación abrupta del proceso tras cada paso del diario/transacción, incluida la restauración de respaldo cuando falle el rename.
- [ ] Añadir pruebas de destino existente, enlaces simbólicos y modificaciones concurrentes reales; el escaneo se ejecuta tras operaciones exitosas.

### P2 — validación en el editor Android
- [ ] Probar en LG K51/Android 11, resolución 720×1600.
- [ ] Confirmar que el dock se muestra y no bloquea el editor.
- [ ] Verificar captura de pantalla, latencia, uso de memoria y eventos táctiles/teclado.
- [ ] Aprobar y rechazar operaciones desde el diálogo; verificar el resultado recibido por el agente.
- [ ] Probar cierre/reinicio del editor y recuperación de transacciones.

### P3 — puente con ChatGPT, sin API de modelos
- [ ] Confirmar primero la disponibilidad de herramientas MCP de escritura en la cuenta/interfaz que se vaya a utilizar.
- [ ] Diseñar un servidor MCP remoto con herramientas mínimas: estado de conexión, identidad del proyecto, análisis/diff, propuesta de una operación y espera de su resultado.
- [ ] Hacer que el servidor MCP use el cliente agente existente y el relay; nunca exponer el token del relay a la conversación.
- [ ] Mantener confirmación del lado de Godot y devolver un resultado inequívoco: aplicado, rechazado, conflicto o error.
- [ ] Probar reconexión, timeout, operaciones repetidas y selección incorrecta de proyecto.

### P4 — build móvil
- [ ] Consolidar cambios antes de iniciar la compilación larga.
- [ ] Validar compilación para `armeabi-v7a` y `arm64-v8a`.
- [ ] Solo entonces preparar el APK y hacer prueba física. No usar un APK como sustituto de las pruebas previas.

## Referencias oficiales revisadas

- Godot 4.7 — Android editor: https://docs.godotengine.org/en/4.7/tutorials/editor/using_the_android_editor.html
- Godot 4.7 — `DirAccess.is_link()`: https://docs.godotengine.org/en/4.7/classes/class_diraccess.html
- Godot — `Input.parse_input_event()`: https://docs.godotengine.org/en/4.7/classes/class_input.html
- OWASP — WebSocket Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html
- OpenAI — Custom MCP servers in ChatGPT: https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt

## Regla para declarar éxito

No marcar Live Link como terminado hasta que se demuestre el flujo completo: ChatGPT/herramienta autorizada → agente → relay → proyecto Godot seleccionado → aprobación explícita → cambio de archivo → resultado verificado; además de pruebas de Android ARM32/ARM64 y una prueba física del editor.
