# Sistema de dos copias de código fuente de Godot

Fecha: 2026-10-27  
Rama de trabajo: `feature/github-sync-and-safe-mcp`  
Release persistente: [godot-modified-core-slots](https://github.com/decuvilan-lgtm/Godot-engine4-v4.7.2-stable-difusion-modificado/releases/tag/godot-modified-core-slots)

## Qué son las dos copias

Son dos archivos comprimidos del **código fuente modificado del editor nativo Godot 4.7.2 para Android**. No son dos APK, ni dos proyectos distintos, ni una aplicación sustituta.

- **`godot-core-posterior.tar.gz` — copia actual:** contiene la versión de fuente más reciente que superó las validaciones configuradas.
- **`godot-core-anterior.tar.gz` — copia previa:** conserva la versión que era la copia actual antes de la última rotación completada.

Cada archivo incluye `godot-source/`, los scripts de integración, los workflows, el README y `godot-core-manifest.json`. El manifiesto registra el commit de Godot oficial, el commit del repositorio modificado, la fecha UTC y hashes SHA-256 de los scripts/addons. No se incluyen `.git`, los binarios generados de `bin/` ni los resultados de compilación.

## Regla de rotación

Cuando una actualización supera el control que le corresponde:

1. Se prepara un archivo temporal con el código fuente y el manifiesto de esa revisión.
2. Si ya existe una copia posterior, se copia esa versión a **anterior**, reemplazando la anterior más vieja.
3. La nueva versión validada pasa a ser **posterior**, reemplazando la posterior vieja.
4. Se elimina el asset temporal. Si la operación falla, el workflow debe marcarse como fallido; no se debe anunciar la rotación como completada sin comprobar los assets del release.

En la primera rotación solo existe la copia posterior; la copia anterior se crea cuando se completa la siguiente rotación. Las dos copias deben pertenecer a revisiones identificables mediante sus manifiestos.

## Qué significa “validada”

- Los pushes normales ejecutan el preflight en **Windows**, incluida la aplicación de los patchers, validadores y carga/parsing de los addons con el editor oficial de Godot 4.7.2 para Windows.
- Una compilación Android completa es un proceso separado. Los pushes ordinarios **no** compilan un APK.
- La validación del preflight confirma los controles automatizados indicados en el workflow; **no demuestra** que cada función se comporte correctamente en el LG K51 Android 11 ni sustituye una prueba real del dispositivo.
- No se deben realizar pruebas en Linux para verificar GDScript o la integración del editor.

## Relación con los APK

El APK instalable, cuando se solicita una compilación Android completa y esta termina con validación satisfactoria, es un artefacto separado. La existencia de una copia posterior del código no implica que exista un APK nuevo. Del mismo modo, que compile un APK no demuestra por sí solo que terreno 3D, controles táctiles, modo inmersivo o sincronización GitHub funcionen correctamente en el teléfono.

## Comprobación después de cada ejecución

1. Revisar que la ejecución de GitHub Actions haya terminado con éxito.
2. Abrir el release y comprobar los nombres de los assets.
3. Confirmar que `godot-core-posterior.tar.gz` corresponde al commit nuevo mediante `godot-core-manifest.json`.
4. Si ya había una copia posterior, comprobar que `godot-core-anterior.tar.gz` corresponde al commit que antes ocupaba posterior.
5. Si falta un asset o los commits no coinciden, informar del fallo concreto y corregir la rotación antes de darla por terminada.
