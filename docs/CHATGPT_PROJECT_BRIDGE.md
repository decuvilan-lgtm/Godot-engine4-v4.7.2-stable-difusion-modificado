# ChatGPT Project Bridge — objetivo y arquitectura

**Estado: especificación de implementación; todavía no es una función operativa.**

## Objetivo de producto

El usuario trabaja desde ChatGPT y selecciona uno de sus proyectos Godot Android. ChatGPT puede crear y modificar los archivos reales del proyecto —escenas, scripts, recursos y configuración— y el editor Godot seleccionado recibe esos cambios automáticamente. El objetivo principal NO es transmitir la pantalla ni simular clics en un segundo editor.

La aplicación debe seguir siendo el Godot Engine 4.7.2 Android modificado; no se crea un editor sustituto. La integración debe conservar el funcionamiento nativo de Godot, GitHub Sync y Terreno 3D.

## Flujo deseado

1. El usuario habilita el puente y elige explícitamente un proyecto local.
2. Godot registra un identificador persistente por proyecto, separado del nombre de carpeta y del nombre visible.
3. La sesión autorizada de ChatGPT obtiene las capacidades del proyecto seleccionado y propone operaciones de archivos.
4. El puente recibe operaciones versionadas y limitadas al directorio del proyecto.
5. El receptor valida ruta, tamaño, hash, versión base y tipo de recurso; prepara una copia temporal y conserva respaldo del archivo previo.
6. La escritura se confirma de forma atómica cuando la plataforma lo permite. Los recursos nuevos o modificados se notifican al FileSystem de Godot para que se reimporten.
7. La operación devuelve estado verificable: aplicada, rechazada, en conflicto o fallida. No se declara éxito solo porque se envió un mensaje.
8. La siguiente operación solo se dirige al proyecto que el usuario tiene autorizado; cambiar de proyecto invalida la autorización anterior para evitar escrituras cruzadas.

Los cambios son directos y automáticos por defecto, según la decisión del usuario. No debe añadirse un flujo de aprobación manual por operación como modo principal. Las comprobaciones de seguridad, las copias de respaldo y la detección de conflicto son automáticas. Si una operación es destructiva o no puede recuperarse de forma segura, se rechaza en vez de borrar silenciosamente datos.

## Separación de responsabilidades

- **ChatGPT / cliente autorizado:** genera o edita los contenidos del proyecto y solicita operaciones usando la interfaz del puente. Debe existir un mecanismo real y autenticado para que esta sesión llegue al puente; un complemento Godot por sí solo no concede acceso al sistema de herramientas de ChatGPT.
- **Puente de transporte:** autentica sesión, proyecto y permisos; limita frecuencia/tamaño; entrega operaciones y confirmaciones. No necesita transportar vídeo ni eventos de ratón para editar archivos.
- **Complemento/integración nativa de Godot:** mantiene el registro de proyectos permitidos, aplica operaciones en la raíz correcta, respalda versiones, actualiza el FileSystem y comunica resultados.
- **GitHub Sync:** sigue siendo una función independiente, unidireccional desde GitHub hacia Godot, a menos que el usuario pida explícitamente otro comportamiento. No debe convertirse silenciosamente en un sistema de subida local a GitHub.

## Protocolo mínimo de operaciones

Cada operación debe incluir: versión de protocolo, ID de proyecto, ID de operación idempotente, tipo (`create`, `update`, `rename`, `delete`), ruta relativa normalizada, hash esperado del contenido, hash de la versión base, tamaño y sesión de origen.

Reglas obligatorias:

- Rechazar rutas absolutas, `..`, separadores ambiguos, enlaces simbólicos que escapen del proyecto y escrituras fuera de la raíz autorizada.
- Excluir por defecto `.git/`, `.godot/`, cachés, temporales, archivos generados y secretos.
- Aplicar límites de tamaño y fragmentar transferencias grandes.
- Verificar hash antes de confirmar y usar escritura temporal más reemplazo atómico.
- Si el hash local ya no coincide con la versión base, preservar ambas versiones y registrar un conflicto; no sobrescribir a ciegas.
- Mantener copias de seguridad recuperables para cambios y borrados. El borrado de un archivo que no puede verificarse debe rechazarse.
- Evitar operaciones duplicadas y permitir reintentos tras desconexiones.
- No almacenar tokens en logs ni incluirlos en mensajes de error.
- Usar WSS para conexiones remotas; permitir WS solo en loopback exacto para desarrollo local.
- Nunca exponer un endpoint de escritura a Internet sin autenticación fuerte, autorización por proyecto y límites.

## Cómo se conecta con ChatGPT

La conexión con ChatGPT no debe darse por hecha por instalar un addon. Se debe elegir e implementar un canal verificable:

1. **Conector/cliente autorizado de herramientas** que permita a ChatGPT solicitar operaciones contra un servicio autenticado; o
2. **Repositorio remoto elegido por el usuario** como transporte inicial: ChatGPT modifica los archivos de ese repositorio y el Godot Android seleccionado los recibe mediante GitHub Sync.

La opción 2 puede reutilizar capacidades existentes, pero no equivale a editar archivos locales arbitrarios sin sincronización. Para cumplir el objetivo de edición directa sin GitHub como paso obligatorio, la opción 1 necesita un cliente/herramienta accesible desde esta sesión y un endpoint real. No afirmar que la integración está completa hasta probar esa ruta de extremo a extremo.

## Plan de implementación y pruebas

1. Inventariar el estado actual y mantener aislada la función experimental de pantalla/entrada.
2. Definir registro y selección de proyectos con permisos por proyecto.
3. Implementar el protocolo de operaciones y el receptor seguro, primero con fixtures y proyectos temporales.
4. Integrar refresco/reimportación de recursos con las APIs soportadas por Godot 4.7.2; comprobar escenas, scripts, UID y referencias.
5. Probar creación, modificación, renombrado, borrado respaldado, operación duplicada, rutas maliciosas, archivo grande, desconexión, conflicto concurrente y cambio de proyecto.
6. Probar con un cliente autorizado real de ChatGPT. Si no existe ese canal en la sesión, dejarlo explícitamente como bloqueo, no simular la conexión.
7. Ejecutar pruebas estáticas y CI, después compilación C++ y finalmente Android ARM32/ARM64 y LG K51. No generar APK ni fusionar antes de consolidar los cambios y completar la auditoría.

## Criterios de aceptación

- Una solicitud desde ChatGPT modifica el proyecto seleccionado, no un proyecto de prueba ni otro proyecto local.
- Godot incorpora y muestra los cambios automáticamente sin tener que pulsar un botón de aplicación por cada cambio.
- El editor sigue siendo utilizable y los recursos modificados se actualizan sin reiniciar el proyecto cuando las APIs lo permitan.
- No hay pérdida silenciosa de archivos ni escritura fuera de la raíz autorizada.
- Se demuestra el flujo completo con un cliente real; pruebas unitarias o una conexión de dos editores no bastan.
- GitHub Sync y Terreno 3D continúan funcionando.
- La documentación distingue siempre prototipo, pruebas simuladas y validación real en Android.

## Estado actual conocido

La rama `feature/live-editor-link` contiene un complemento experimental que envía capturas y reenvía eventos de entrada mediante un relay. La CI ha validado varias pruebas de relay, el parseo/carga de los addons y partes del generador de instalación. Eso **no** prueba escritura/sincronización de archivos, conexión directa desde ChatGPT, compilación C++ ni ejecución Android. El protocolo de sincronización anterior es una propuesta y debe alinearse con este objetivo de puente ChatGPT→proyecto.
