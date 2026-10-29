# Live Link para Godot Android

Complemento experimental opcional para enlazar dos editores Godot mediante un relay WebSocket autenticado. La pantalla remota se muestra en un dock y los eventos de ratón, teclado y toque se reenvían al otro editor.

## Estado y límites

- Este addon no se activa por sí solo: debe instalarse y habilitarse en un proyecto/editor que lo incluya.
- El complemento de proyecto no puede capturar todas las superficies nativas de Android ni garantizar que cada menú del editor responda a eventos sintetizados. La integración global en el editor Android requiere un cambio nativo adicional y una prueba en el dispositivo.
- La captura de la raíz del SceneTree puede omitir ventanas/paneles nativos o no representar el framebuffer completo. Esto debe validarse en Android.
- La conexión remota concede control de entrada al participante autorizado. Usar solo con un relay privado, token fuerte y WSS. No exponer un relay de desarrollo a Internet.
- El dock oculta el código hasta que se pulsa «Revelar código identificador»; cada revelado desconectado genera un nuevo ID aleatorio de 128 bits y lo guarda en `ProjectSettings`, evitando que copias del mismo proyecto compartan accidentalmente el destino. El ID no puede cambiar mientras se conecta o está conectado. «Copiar código», «Habilitar conexión (sin activarla)» y «Activar conexión» son pasos separados. Revelar/copiar el ID no conecta ni autoriza operaciones por sí solo.
- El addon ya contiene un receptor experimental para operaciones `create`, `update`, `rename` y `delete` dirigidas al ID de proyecto seleccionado. Valida el ID y la envoltura de operación antes de pedir aprobación, limita las rutas al proyecto, comprueba SHA-256, crea copias de seguridad antes de reemplazar o eliminar y solicita un escaneo del sistema de archivos de Godot. El relay transporta estas operaciones desde un rol `agent` autenticado. La comprobación de enlaces simbólicos usa `DirAccess.is_link()` cuando la plataforma la implementa; la documentación oficial de Godot 4.7 enumera macOS, Linux y Windows, no Android, por lo que **no debe considerarse una garantía de seguridad en Android**. Para uso remoto real, el proyecto debe mantenerse en una ubicación administrada por el editor y todavía se necesita una protección nativa Android o una prueba de ruta equivalente antes de afirmar resistencia completa a enlaces simbólicos.
- La CI valida el protocolo del relay y carga el complemento con Godot 4.7.2 headless; las pruebas de rutas y transacciones son en parte comprobaciones estáticas del código. **Todavía no demuestran operaciones de archivos reales, recuperación tras cierre forzado ni entrada/captura en el teléfono Android**.
- El relay y `relay/agent_client.py` no conectan por sí solos ChatGPT al editor. La arquitectura directa necesita un servidor MCP remoto compatible con ChatGPT que invoque al cliente agente y use el relay; no requiere llamar a la API de modelos de OpenAI, pero sí depende de la disponibilidad de conectores MCP de escritura en ChatGPT y de un endpoint remoto seguro. ChatGPT no se conecta directamente a un servidor MCP local desde la app móvil. Hasta implementar y probar ese puente, **no existe una conexión ChatGPT→Godot de extremo a extremo**.

## Ajustes

Los ajustes de URL, sala y rol se guardan en el proyecto. El token se guarda en EditorSettings del usuario, no en project.godot, y puede leerse desde LIVE_LINK_TOKEN.

El relay de desarrollo asociado está separado de este complemento y debe desplegarse/configurarse por separado. No hay un servidor desplegado automáticamente por este addon.
