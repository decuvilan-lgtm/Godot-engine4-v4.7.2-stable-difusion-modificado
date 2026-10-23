# Godot Android Editor 4.7.2 — proyecto móvil

## Objetivo

Mantener y ampliar el **editor oficial de Godot 4.7.2 para Android**, con una interfaz cómoda en pantalla móvil y compatibilidad con:

- Android 11 o superior compatible con el editor.
- ARM32: `armeabi-v7a`.
- ARM64: `arm64-v8a`.
- Dispositivo prioritario de prueba: LG K51 con Android 11.

La aplicación entregada es el editor Android completo. La infraestructura remota de automatización, si se utiliza para compilar el APK, es únicamente una herramienta de desarrollo; no es parte de la aplicación.

## Reglas del proyecto

1. **GitHub → Godot únicamente.** La sincronización nunca sube archivos locales ni cambios del proyecto a GitHub.
2. Analizar primero, revisar después y aplicar cambios solo tras confirmar que el commit remoto y los archivos locales siguen iguales a los revisados.
3. No sobrescribir archivos editados localmente sin protección. Si un archivo rastreado fue modificado localmente y GitHub lo elimina, moverlo a una carpeta de recuperación fuera del proyecto, conservando su ruta y contenido.
4. Los cambios de sincronización deben aplicarse como una transacción verificable, con respaldo y reversión ante fallos.
5. Importar proyectos completos preservando estructura, escenas independientes, instancias, escenas heredadas, recursos, señales y dependencias.
6. Los avisos propios de archivos dañados se reservan para errores reales de lectura o corrupción. Los errores de sintaxis, ejecución y referencias siguen apareciendo en Output/Debugger de Godot.
7. La interfaz debe ser táctil y adaptarse a pantallas móviles de alrededor de 720 × 1600. Reutilizar Output y Debugger nativos, sin duplicarlos.
8. No declarar funciones terminadas por pruebas de código únicamente. Separar claramente validación estática, compilación del APK, comprobaciones del paquete y pruebas reales en el teléfono.

## Funciones y estado real

### Importación de GitHub

El parche nativo de Project Manager incorpora el flujo de importación de repositorios públicos, búsqueda separada y paginación de resultados, además de selección opcional de rama, etiqueta o commit. El usuario confirmó previamente que la búsqueda pública, la importación de su propio repositorio y la ejecución del proyecto importado funcionaban en su teléfono. Las variantes de ref explícita, paginación y recuperación ante fallos de red requieren pruebas adicionales.

### Análisis y revisión de sincronización

El parche de Project Manager compara hashes Git de archivos locales con el árbol remoto, fija el commit y permite volver a validar la revisión mediante huellas del inventario local y remoto. **Es una comparación de solo lectura. La sincronización nativa transaccional todavía no está integrada; el botón de sincronización permanece deshabilitado.**

### Recuperación de archivos

El núcleo de sincronización en Python contiene planificación, manifiestos, aplicación transaccional y recuperación de archivos editados localmente que fueron eliminados remotamente. Tiene pruebas unitarias automatizadas. **Este núcleo todavía no está conectado al escritor nativo del editor Android**, por lo que no debe presentarse como una función disponible en la aplicación.

### Importación consciente de escenas

Existe un planificador auxiliar para dependencias textuales explícitas y pruebas de estructura de escenas. La integración completa debe usar los cargadores de recursos nativos de Godot para resolver dependencias y preservar cada escena en su propio archivo. La integración nativa completa y las pruebas en Android siguen pendientes.

### Diagnóstico de archivos dañados

Existe un clasificador auxiliar que separa errores reales de lectura/decodificación/contenedor de errores normales de scripts o referencias. Aún falta conectarlo a la interfaz nativa de Android.

### MCP y vista previa

El paquete MCP se prepara para incluirse dentro del APK Android. Las funciones de control del editor, organización de escenas, interacción con controles y control de una partida en ejecución deben considerarse pendientes de validación integral en Android hasta comprobar el paquete final y el comportamiento real.

## Compilación y entrega Android

Workflow: [Build Godot Android Editor](.github/workflows/build-godot-android-source.yml)

La compilación prevista genera un APK completo del editor Godot 4.7.2 para ARM32 y ARM64. El flujo comprueba que el APK exista, que no sea un paquete intermedio pequeño, que contenga ambas arquitecturas, que el ZIP sea íntegro, que la firma sea válida y que el alineamiento sea correcto. Los artefactos se publican en GitHub Actions.

No se debe reutilizar un APK antiguo como evidencia de que cambios recientes ya están incluidos. Cada entrega debe vincularse a su commit y ejecución de compilación exactos.

## Rama activa

`work/mobile-ui-preflight`

## Pendientes prioritarios

1. Integrar el flujo transaccional de sincronización en el editor nativo Android y habilitar Sync solo cuando esté completo.
2. Conectar la recuperación de archivos eliminados remotamente y modificados localmente, guardándolos fuera del proyecto.
3. Completar la importación de escenas usando el cargador nativo de recursos.
4. Conectar el clasificador de corrupción real a los avisos nativos sin duplicar Output/Debugger.
5. Validar las funciones integradas, compilar el APK ARM32+ARM64 y probarlo en el LG K51 antes de declarar cada función lista.

**Este documento distingue explícitamente los auxiliares de código, la integración nativa pendiente y las funciones probadas en el teléfono.**
