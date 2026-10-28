# Live Link para Godot Android

Complemento experimental opcional para enlazar dos editores Godot mediante un relay WebSocket autenticado. La pantalla remota se muestra en un dock y los eventos de ratón, teclado y toque se reenvían al otro editor.

## Estado y límites

- Este addon no se activa por sí solo: debe instalarse y habilitarse en un proyecto/editor que lo incluya.
- El complemento de proyecto no puede capturar todas las superficies nativas de Android ni garantizar que cada menú del editor responda a eventos sintetizados. La integración global en el editor Android requiere un cambio nativo adicional y una prueba en el dispositivo.
- La captura de la raíz del SceneTree puede omitir ventanas/paneles nativos o no representar el framebuffer completo. Esto debe validarse en Android.
- La conexión remota concede control de entrada al participante autorizado. Usar solo con un relay privado, token fuerte y WSS. No exponer un relay de desarrollo a Internet.
- No comparte archivos automáticamente, no sustituye GitHub Sync ni el guardado del proyecto.

## Ajustes

Los ajustes de URL, sala y rol se guardan en el proyecto. El token se guarda en EditorSettings del usuario, no en project.godot, y puede leerse desde LIVE_LINK_TOKEN.

El relay de desarrollo asociado está separado de este complemento y debe desplegarse/configurarse por separado. No hay un servidor desplegado automáticamente por este addon.
