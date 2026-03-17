# Guía de Contribución para ChambaFlow 🚀

¡Gracias por tu interés en contribuir a **ChambaFlow**! Todas las contribuciones (desde solucionar un pequeño error tipográfico hasta agregar un nuevo sitio web de empleos) son bienvenidas y valoradas.

Esta guía te ayudará a empezar de forma rápida y sencilla.

## 🤝 Cómo Contribuir

### 1. Reportando Bugs o Sugiriendo Funcionalidades
- Revisa los [Issues](https://github.com/IsrraDex36/chambaflow/issues) existentes para asegurarte de que tu sugerencia o error no haya sido reportado ya.
- Si no existe, abre un nuevo *Issue* usando la plantilla correspondiente (si aplica), o proporcionando tantos detalles como sea posible (sistema operativo, versión de Python, navegador, logs, etc.).

### 2. Haciendo Cambios en el Código (Pull Requests)
Si quieres arreglar un bug o añadir una nueva característica (por ejemplo, un nuevo bot para *Indeed* o *LinkedIn*), sigue estos pasos:

1. **Haz un Fork** del repositorio a tu cuenta de GitHub.
2. **Clona** tu fork localmente:
   ```bash
   git clone https://github.com/TU_USUARIO/chambaflow.git
   cd chambaflow
   ```
3. **Crea una nueva rama** descriptiva para tu cambio:
   ```bash
   git checkout -b feature/nombre-de-tu-funcionalidad
   # o
   git checkout -b fix/descripcion-del-error
   ```
4. **Instala las dependencias**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Haz tus cambios**. Asegúrate de que el código sigue un estilo limpio (PEP 8) y que, si es necesario, actualizas la documentación y el archivo `config.example.yaml`.
6. **Haz commit** de tus cambios usando mensajes claros. Un buen formato es `tipo: breve descripción` (ej. `feat: agregar soporte para Indeed` o `fix: corregir selector de CSS en OCC`).
7. **Sube tus cambios** a tu fork:
   ```bash
   git push origin feature/nombre-de-tu-funcionalidad
   ```
8. **Abre un Pull Request (PR)**:
   - Ve a la página principal del repositorio original (`IsrraDex36/chambaflow`).
   - GitHub te mostrará un botón verde para "Compare & pull request". Haz clic.
   - Describe claramente qué soluciona o aporta tu PR.

### 3. Estilo de Código (Python)
- Usamos la convención PEP 8.
- Utiliza nombres de variables y funciones descriptivos (en inglés o español, pero mantén consistencia con el archivo que estás editando).
- Si agregas una nueva dependencia a tu bot, no olvides incluir un comentario explicando por qué es necesaria en el PR.

## 🛠 Entorno de Desarrollo

Recuerda que para hacer pruebas locales de un bot nuevo o un cambio, es altamente recomendado usar el modo de *depuración del navegador*. Asegúrate de no subir tu archivo `config.yaml` o carpetas de `session_data` (revisa el `.gitignore`).

¡De nuevo, muchas gracias por ayudar a que esta herramienta sea mejor para todos! 🙌
