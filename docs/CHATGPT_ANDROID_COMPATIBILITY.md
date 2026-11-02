# Política de compatibilidad Android para ChatGPT

Este contrato es la referencia obligatoria para cualquier cliente/agent que envíe cambios a través de Live Link. La fuente legible por máquina está en [android_capabilities.json](../scripts/live_link_addon/android_capabilities.json).

## Regla principal

ChatGPT debe trabajar sobre el **Godot 4.7.2 modificado que corre en Android**, no sobre una suposición de que está usando el editor de escritorio. Las funciones exclusivas de PC no deben ser requisito para crear, modificar, probar o controlar el proyecto Android.

Perfil objetivo: LG K51, Android 11, resolución de referencia 720×1600 y arquitecturas ARM32 (`armeabi-v7a`) y ARM64 (`arm64-v8a`). La experiencia principal es móvil y táctil.

## Comportamiento obligatorio del agente

- Leer el manifiesto de capacidades antes de proponer o enviar operaciones.
- Preferir escenas, nodos, recursos y APIs compatibles con Android y con la versión exacta del motor.
- No asumir que un menú, dock, ventana, atajo de teclado o API del editor de escritorio existe en el editor Android.
- No introducir dependencias, ejecutables, rutas, comandos de shell ni binarios solo para Windows/Linux/macOS en el flujo Android.
- Si una API de `EditorPlugin`, `EditorInterface`, archivos, ventanas, portapapeles, entrada, renderizado o hilos no tiene compatibilidad comprobada, verificarla en el código fuente de esta rama antes de usarla y marcarla como pendiente si no puede probarse.
- Mantener controles táctiles y legibles en móvil. No sustituir el editor nativo ni eliminar opciones existentes de Godot.
- Los cambios nativos deben conservar compatibilidad con Android ARM32 y ARM64; no basta con que compilen en Linux.
- No generar APK hasta consolidar y auditar los cambios.
- En Live Link, aplicar cambios solo al ID de proyecto autorizado y esperar una confirmación explícita del editor para declarar una operación completada.

## Diferencia importante

La compatibilidad del **juego exportado a Android** no garantiza que una función esté disponible dentro del **editor Godot ejecutándose en Android**. El agente debe comprobar ambas capas por separado. El manifiesto es una política de trabajo, no una prueba automática de compatibilidad ni una conexión de ChatGPT ya operativa.

## Estado actual

La política queda definida para orientar el futuro cliente de ChatGPT. Todavía falta que el cliente real lea este manifiesto y lo aplique automáticamente antes de generar operaciones; no se debe presentar esa integración como terminada hasta añadirla y probarla.
