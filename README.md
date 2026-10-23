# Godot Android Editor 4.7.2 — guía de trabajo del proyecto

## Misión

Construir y verificar una versión modificada del **editor real de Godot 4.7.2 para Android**, usable desde el celular. No convertirlo en una app auxiliar ni reemplazar el editor por otra herramienta.

- Dispositivo de prueba prioritario: **LG K51, Android 11**.
- Arquitecturas requeridas en el APK: **ARM32 (`armeabi-v7a`) y ARM64 (`arm64-v8a`)**.
- Interfaz táctil adaptada a pantallas de aproximadamente 720 × 1600.
- La infraestructura Linux/Windows usada por GitHub Actions, si la hay, solo sirve para preparar o validar el APK. **No añadir funciones del producto exclusivas de PC ni presentar pruebas de escritorio como pruebas de Android.**

Rama de base estable: `work/mobile-ui-preflight`. Rama actual de implementación sin compilaciones automáticas: `feature/native-editor-integration`.

## Prioridades de ejecución

**No iniciar otra compilación completa de Android durante la fase de implementación.** Una compilación ARM32+ARM64 tarda aproximadamente una hora. Primero terminar y revisar los cambios de código; compilar una sola vez cuando las modificaciones planeadas estén integradas. La prueba final de instalación y uso sigue correspondiendo al usuario en el LG K51.

1. Terminar la integración nativa de GitHub: revisión fijada al commit, manifiesto persistente, conflictos, recuperación de cambios locales, transacción y rollback. Sync seguirá deshabilitado hasta cumplir las garantías.
2. Completar la importación de escenas con dependencias usando los cargadores nativos de Godot; preservar rutas, instancias, escenas heredadas, señales y grupos.
3. Conectar las alertas de corrupción real al flujo nativo de lectura, sin duplicar Output/Debugger.
4. Completar y verificar el control MCP del editor y de la vista previa: navegación de UI, escena/nodos, controles de ejecución y juego en ejecución.
5. Revisar la adaptación móvil y ejecutar pruebas estáticas de todas las modificaciones.
6. Solo entonces generar un APK ARM32+ARM64 y detenerse para la prueba real en el LG K51.

No repetir listas de mejoras sin implementar trabajo. No afirmar que una función está terminada hasta reunir la evidencia correspondiente.

## Reglas que no se deben romper

1. **Solo GitHub → Godot.** Nunca subir proyectos ni cambios locales del usuario a GitHub como parte de la sincronización.
2. Analizar primero; después mostrar una revisión legible; aplicar solo si el repositorio está fijado a un commit concreto y los inventarios locales/remotos siguen iguales a los revisados.
3. Nunca sobrescribir silenciosamente archivos locales editados ni borrar archivos no rastreados.
4. Si GitHub elimina un archivo rastreado que fue modificado localmente, preservar su contenido fuera del proyecto, dentro de una carpeta de recuperación en el dispositivo, conservando la ruta relativa. Solo borrar normalmente archivos remotos eliminados cuando se haya verificado que no tienen cambios locales.
5. La aplicación de cambios debe ser transaccional: verificar rutas y huellas, crear respaldo, comprobar escrituras y restaurar ante un fallo. Si estas garantías no están integradas en el editor Android, Sync debe permanecer deshabilitado.
6. Importar proyectos completos: conservar estructura, escenas como archivos separados, instancias, escenas heredadas, recursos, señales, grupos y dependencias.
7. Alertar sobre archivos dañados únicamente ante errores reales de lectura, decodificación o contenedor. Los errores de sintaxis, ejecución y referencias deben seguir en Output/Debugger nativos de Godot; no crear un segundo sistema que los duplique.
8. Los botones, menús y paneles deben ser táctiles, caber en la pantalla móvil y evitar popups molestos que tapen controles.
9. MCP debe funcionar de forma explícita y segura. No instalar ni activar complementos sin validación del paquete y sus permisos.
10. Nunca publicar un APK como listo ni crear una release sin aprobación del usuario.

## Estado verificado y límites

### Búsqueda/importación de GitHub

El parche fuente añade un diálogo para repositorios públicos, búsqueda separada, paginación y una referencia opcional (rama, etiqueta o commit). Se detectó y corrigió el flujo del campo de texto: enviar desde el teclado con «Listo» ahora inicia la búsqueda de respaldo, en lugar de intentar directamente la descarga.

- Validación estática de anclajes y pruebas auxiliares: **correcta** en la ejecución de GitHub Actions del commit `200ac68b880dfb5eea596d646a9893e865206bcf`.
- La corrección aún necesita un APK recompilado y una prueba real en Android. **No asumir que ya funciona en el teléfono.**
- Si falla, inspeccionar el resultado HTTP, el JSON de GitHub, el foco/teclado y las señales de `HTTPRequest`; corregir la causa y repetir las pruebas, no limitarse a cambiar el README.

### Análisis/revisión de sincronización

El parche nativo proporciona una interfaz de análisis de solo lectura, fija el commit remoto y valida huellas de la revisión. **No es sincronización de archivos.** El escritor transaccional no está integrado en el Project Manager Android y Sync debe permanecer deshabilitado.

### Núcleo auxiliar de sincronización

`scripts/github_sync_core.py` y sus pruebas cubren planificación, manifiestos, protección de archivos locales y recuperación de archivos editados que GitHub elimina. `scripts/github_sync_review.py` aporta validación de una revisión fijada a repositorio, proyecto y commit. Son auxiliares Python probados; **no son todavía una función disponible en el editor Android**, porque falta conectarlos al flujo nativo de escritura.

La carpeta de recuperación debe quedar fuera de la raíz del proyecto y en almacenamiento que el editor Android pueda usar de forma fiable. Antes de integrar, verificar permisos, rutas reales en Android, límites de almacenamiento y recuperación tras interrupciones.

### Importación de escenas

Hay herramientas auxiliares y fixtures de validación, pero no equivalen a la integración completa con los cargadores de recursos de Godot. No resolver dependencias únicamente buscando texto en archivos: las rutas externas, UID, recursos importados y escenas heredadas requieren manejo nativo y pruebas con proyectos reales.

### Avisos de corrupción

Existe un clasificador auxiliar; todavía debe conectarse al flujo nativo. Mantener separados los errores de archivos ilegibles de los errores normales de scripts, recursos faltantes o ejecución.

### MCP y vista previa

El paquete MCP endurecido ya incluye herramientas tipadas para inspeccionar y activar controles de la interfaz del editor, abrir/ejecutar escenas, modificar nodos con undo/redo, leer diagnósticos y controlar un juego mediante un puente de ejecución local. La nueva herramienta `inspect_scene_dependencies` usa `ResourceLoader.get_dependencies()` para construir un grafo acotado y de solo lectura, incluyendo recursos binarios cuando el cargador los expone. Esto **inspecciona dependencias; todavía no es el importador nativo de escenas desde GitHub**. Todo el conjunto requiere pruebas de empaquetado y uso real antes de declararse listo.

## Compilación y comprobación

Workflow principal: [Build Godot Android Editor](.github/workflows/build-godot-android-source.yml).

Validación de fuentes y pruebas auxiliares: [Validate Android source patch anchors](.github/workflows/validate-android-patch-anchors.yml).

La validación estática revisa sintaxis, anclajes y pruebas Python; **no compila ni ejecuta el editor Android**. Para cada APK, anotar el commit fuente, el ID de ejecución de Actions, el artefacto, el tamaño, la firma y las arquitecturas incluidas. Rechazar APK intermedios, paquetes antiguos o builds de un commit distinto.

La aceptación final requiere instalar y probar el APK en Android. Si no se tiene evidencia de una prueba en el LG K51, indicarlo como pendiente, no como éxito.

## Próximos pasos concretos

1. Integrar el escritor transaccional de GitHub en el editor nativo y mantener Sync deshabilitado hasta superar sus pruebas.
2. Conectar el cierre de dependencias de escenas al flujo real de importación de Godot, no limitarse al grafo de inspección MCP.
3. Conectar el clasificador de corrupción a errores de lectura nativos.
4. Validar todas las herramientas MCP y los controles de vista previa incluidos en el paquete.
5. Ejecutar validaciones estáticas sin disparar una compilación Android en cada commit de implementación.
6. Compilar una sola vez cuando el conjunto esté listo y entregar el APK para la prueba real en el LG K51.

**Principio de trabajo:** avanzar con cambios comprobables, proteger los proyectos del usuario y priorizar el funcionamiento móvil real sobre añadir más funciones.
