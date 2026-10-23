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

## Funciones adicionales que no vienen de serie en Godot

Estas son ampliaciones propias del editor Android y de su complemento MCP; no deben confundirse con funciones incluidas en Godot original. El objetivo es que una IA pueda operar el editor y probar el juego mediante herramientas tipadas, sin habilitar ejecución arbitraria de código.

| Opción personalizada | Qué debe aportar | Estado honesto |
|---|---|---|
| Buscar/importar repositorios GitHub | Buscar repositorios públicos, actualizar resultados y traer proyectos hacia Godot; permitir rama, etiqueta o commit | El flujo de búsqueda existente requiere prueba real en Android. El nuevo importador aditivo tiene parche fuente y validación estática inicial; todavía no está compilado ni probado en el teléfono. |
| Conexión de proveedores de IA | Presets para proveedores como ChatGPT/GPT y Grok, conexión autorizada y detección de herramientas MCP por el cliente | Plan previsto; todavía no implementado. La conexión oficial/API debe configurarse explícitamente; tener una suscripción de ChatGPT no implica disponer de acceso a la API. No guardar claves en el repositorio. |\n| Control de interfaz del editor por MCP | Inspeccionar controles, abrir menús, cambiar pestañas/opciones y activar controles accesibles de la interfaz | Herramientas tipadas añadidas al paquete fuente; cobertura parcial y pruebas de ejecución pendientes. No equivale a controlar todos los menús o complementos. |
| Control de la escena por IA | Consultar estado, abrir/ejecutar escenas, leer propiedades, crear recursos y organizar nodos, grupos y señales con undo/redo | Parte de las herramientas existe en el código del complemento; pruebas de parser y funcionamiento real pendientes por herramienta. |
| Encontrar y probar controles del juego | Enumerar controles de la escena y, con el puente de ejecución instalado, localizar controles vivos e interactuar con botones, campos, deslizadores y opciones | El puente de juego en ejecución es código fuente añadido; falta probar el intercambio MCP y el comportamiento real en Android. |
| Entrada de juego y pantalla completa | Enviar clics, teclado, toques y gestos al juego en ejecución; pedir pantalla completa y volver al modo anterior | Diseñado mediante el puente local del proyecto; no se declara funcional hasta confirmar respuesta y cambio visual en el dispositivo. No controla diálogos nativos de Android. |
| Visualización de depuración: formas de colisión | Primer control aislado: activa/desactiva el dibujo nativo de colisiones durante una sesión de depuración; estado del interruptor y mensajes de diagnóstico en Output. No añade scripts ni modifica el proyecto. | Parche fuente con transición forzada del backend para refrescar formas existentes; la validación estática del último commit está en curso. Sin compilación C++ ni prueba visual en Android. Rutas, navegación y demás opciones permanecen ocultas hasta implementar y validar cada una por separado. |
| Inspección de dependencias de escenas | Recorrer dependencias mediante el cargador nativo de recursos de Godot, incluso recursos no textuales cuando se exponen | La herramienta de inspección MCP está añadida; importar automáticamente el cierre completo de dependencias desde GitHub aún requiere integración nativa. |
| Avisos de archivos realmente dañados | Detectar fallos de lectura, decodificación o contenedor ilegible | Hay un clasificador auxiliar; falta conectarlo al flujo nativo. Los errores normales de scripts siguen en Output/Debugger y no se duplican. |
| Revisión y sincronización GitHub → Godot | Comparar cambios con el commit revisado y gestionar adiciones, actualizaciones, eliminaciones rastreadas, conflictos y recuperación transaccional | La revisión está en el código nativo. El botón nuevo implementa solo importación aditiva y no sobrescribe archivos existentes; todavía no es la sincronización completa descrita en la arquitectura. |

### Reglas para estas opciones personalizadas

- Mantener controles táctiles accesibles en el diseño móvil de 720 × 1600; no añadir una interfaz de escritorio como solución de producto.
- El puente de juego solo debe escuchar en loopback y usar autenticación; no abrir control remoto sin autenticar en la red.
- No añadir ejecución arbitraria de GDScript/eval para fingir cobertura universal.
- No borrar la raíz de un proyecto ni sobrescribir archivos locales durante la importación aditiva.
- Informar cada herramienta como implementada, parcial, no disponible o bloqueada por seguridad; un archivo generado o un workflow exitoso no demuestra que funcione en el dispositivo.

## Visualización de depuración sin scripts temporales

**Estado: primera opción aislada integrada en el código fuente; falta compilación C++ y prueba visual en Android.** La vista previa incorpora únicamente el interruptor de formas de colisión. Este envía el estado por el protocolo nativo de depuración a `SceneDebugger`, que solicita el hint de colisiones de `SceneTree`. El handler valida el número y tipo del argumento y comprueba si el backend activó el estado solicitado; si no, devuelve un error de depuración en lugar de darlo por hecho. Output también advierte si no existe una sesión activa. Actions aplica el parche al código oficial 4.7.2 y ejecuta comprobaciones estáticas, no compila el motor.

### Física y colisiones
- **Integración de código fuente:** interruptor de formas de colisión en la vista previa, conectado al hint nativo de Godot. Aún sin prueba de compilación o ejecución.
- **Variables y límites cubiertos:** desactivado por defecto; estado booleano explícito; solo acepta un argumento booleano; comprueba sesión de depuración y confirma el estado que informa el backend; falla de forma visible si la compilación/backend no admite la función; cubre el dibujo nativo 2D/3D que ofrezca el backend, sin recorrer nodos ni crear geometría por frame.
- **Rendimiento:** no se añade un proceso por frame, no se escanean nodos, no se crean materiales/meshes ni se alteran físicas; el coste extra queda limitado al dibujo nativo mientras está activado. La visualización puede bajar FPS en escenas con muchas formas, por lo que debe permanecer apagada por defecto.
- **Mitigación nativa añadida:** el manejador fuerza una transición del backend (estado opuesto y luego estado solicitado) para disparar las notificaciones de depuración física que refrescan las formas de colisión ya existentes. Esto evita depender de que el estado previo sea distinto. La documentación de Godot advierte que el hint no está diseñado para cambiarse durante la ejecución; por eso sigue pendiente compilar C++ y confirmar visualmente el resultado en la vista previa real. Referencia oficial: [SceneTree — debug_collisions_hint](https://docs.godotengine.org/en/4.7/classes/class_scenetree.html#class-scenetree-property-debug-collisions-hint).
- **Pendiente:** distinguir áreas/cuerpos, puntos de contacto y normales, RayCast/ShapeCast, capas, máscaras y exclusiones.
- Formas de colisión 2D/3D y formas activas durante la ejecución.
- Áreas `Area2D`/`Area3D` y cuerpos StaticBody, RigidBody y CharacterBody.
- Puntos de contacto y normales, si el depurador nativo lo permite.
- RayCast2D/3D y ShapeCast2D/3D: forma, dirección y resultados reales.
- Capas, máscaras y exclusiones de colisión de los nodos seleccionados.

### Navegación e IA
- **Pendiente; no se exponen todavía en la interfaz.** Se implementarán solo después de terminar y probar la opción de colisiones.
- **Pendiente:** controles separados para mallas, destinos, agentes, obstáculos y visualización específica de detección de enemigos.
- Mallas y regiones de navegación, rutas calculadas, destinos y agentes.
- Obstáculos, trayectorias Path2D/Path3D y seguidores.
- Zonas existentes de visión, alcance y detección de enemigos.
Solo mostrar datos reales de nodos/sistemas existentes; no inventar rutas ni crear comportamientos automáticamente.

### Objetos, nodos y movimiento
- Nombres, rutas e identificadores disponibles de nodos.
- Posiciones locales/globales, rotación, escala, dimensiones y coordenadas del jugador/objeto.
- Rectángulos delimitadores, pivotes, centros, orígenes, ejes locales/globales y orientación 3D.
- Esqueletos/huesos 2D/3D, anclajes, deformación, trayectorias, vectores de velocidad/aceleración/dirección y estado de animación cuando existan datos accesibles.
- Límites y área visible de cámaras, frustum 3D, desplazamiento de cámara, zonas de influencia y activación.

### Interfaz
- Rectángulos de controles y áreas interactivas; anclajes, márgenes y contenedores.
- Guías, cuadrícula, alineación, zona segura móvil y límites visibles de la UI durante la vista previa.

### Herramientas del editor 2D y 3D
- **2D:** cuadrícula/guías, colisiones, límites físicos, pivotes/orígenes, cámaras, rutas y navegación. Solo las formas de colisión tienen ahora una integración de código fuente parcial.
- **3D:** cuerpos y colisiones, contactos/normales cuando sea posible, cámaras/frustum, luces y rangos, ejes/pivotes/orientación, navegación y obstáculos. Estas opciones siguen pendientes.
Si Godot ya ofrece una visualización, exponer un acceso rápido en lugar de duplicarla.

### Menú de la vista previa: “Visualización de depuración”
Interruptores independientes para colisiones, áreas de detección, RayCast/ShapeCast, contactos/normales, navegación/rutas, nombres/rutas de nodos, pivotes/ejes, límites de cámara, movimiento/animaciones y límites de interfaz. Incluir **Activar todas las compatibles**, **Desactivar todas** y **Restablecer valores predeterminados**. Recordar preferencias solo si puede hacerse sin alterar la configuración del proyecto.

### Requisitos y pruebas
1. Investigar primero opciones y APIs disponibles en la versión exacta 4.7.2.
2. No agregar scripts temporales al proyecto ni modificar materiales, colisiones o nodos permanentemente.
3. Etiquetar el alcance de cada opción: **Editor 2D**, **Editor 3D**, **Vista previa/ejecución** o **No compatible**.
4. Si una API no permite mostrar una vista durante la ejecución, decirlo claramente; no simular datos ni afirmar compatibilidad.
5. Mantener controles táctiles aptos para 720 × 1600 y no tapar el juego.
6. Validar primero anclajes y pruebas estáticas en Actions; después probar proyectos 2D y 3D reales y la vista previa Android. Las pruebas estáticas no prueban el comportamiento visual en el dispositivo.

### Orden de implementación
1. Terminar y validar de extremo a extremo el interruptor de formas de colisión (compilación y prueba real de vista previa).
2. Añadir y validar por separado contactos/normales y RayCast/ShapeCast.
3. Añadir y validar por separado navegación/rutas.
4. Continuar con pivotes, nombres, límites, animaciones, cámaras e interfaz, una opción por vez.
5. Probar cada opción en proyectos 2D y 3D reales antes de comenzar la siguiente.

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
