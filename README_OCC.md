# ChambaFlow OCC - Instrucciones de Uso

Guía dedicada para ejecutar el bot en `occ.com.mx`.
Por defecto está configurado para Brave en modo depuración, pero también funciona con otros navegadores Chromium (por ejemplo Chrome o Edge).

## 1) Requisitos

- Python 3.10+ instalado
- Dependencias del proyecto instaladas:

```powershell
pip install -r requirements.txt
```

## 1.1) Instalación rápida

```powershell
git clone https://github.com/IsrraDex36/chambaflow.git
cd chambaflow
pip install -r requirements.txt
```

## 1.2) Primer arranque en 60 segundos

Checklist express:

1. Instala dependencias: `pip install -r requirements.txt`
2. Verifica `config.yaml`:
   - `sitios: ["occ"]`
   - `browser: "brave"` (o `chrome`)
   - `debugger_address: "127.0.0.1:9222"`
3. Abre navegador en debug (`--remote-debugging-port=9222`)
4. Inicia sesión manual en `https://www.occ.com.mx/`
5. Ejecuta: `python -u main.py`
6. Si necesitas detener: usa el comando de la sección **9**

- Tener `config.yaml` configurado para OCC:
  - `sitios: ["occ"]`
  - `browser: "brave"`
  - `debugger_address: "127.0.0.1:9222"`

## 2) Regla clave del flujo

Siempre en este orden:

1. Abrir navegador (Brave) en modo depuración
2. Iniciar sesión manual en OCC
3. Ejecutar el bot

Si no hay navegador en `9222`, el bot no podrá conectarse.

## 3) Abrir Brave en modo depuración

En PowerShell:

```powershell
Start-Process -FilePath "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" -ArgumentList '--remote-debugging-port=9222','--user-data-dir=C:\\Users\\TU_USUARIO\Videos\PRUEBAS-PY\bot\brave_manual_profile'
```

Validación opcional:

```powershell
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9222/json/version', timeout=3).status)"
```

Si imprime `200`, está correcto.

## 3.1) Otros navegadores compatibles (Chromium)

Tambien puedes usar Chrome o Edge.

1. Cambia en `config.yaml`:

```yaml
browser: "chrome"
debugger_address: "127.0.0.1:9222"
```

2. Abre ese navegador con `--remote-debugging-port=9222` y un perfil dedicado.

Ejemplo Chrome en PowerShell:

```powershell
Start-Process -FilePath "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList '--remote-debugging-port=9222','--user-data-dir=C:\\Users\\TU_USUARIO\Videos\PRUEBAS-PY\bot\chrome_manual_profile'
```

## 4) Iniciar sesión en OCC

En la ventana de Brave abierta:

1. Entrar a `https://www.occ.com.mx/`
2. Iniciar sesión manualmente
3. Dejar esa ventana abierta

## 5) Ejecutar el bot

Desde la carpeta del proyecto:

```powershell
python -u main.py
```

`-u` ayuda a ver logs en tiempo real.

## 6) Configuración recomendada (`config.yaml`)

Ejemplo:

```yaml
keywords:
  - "Desarrollador web remoto"
  - "Frontend remoto"
  - "Full stack remoto"
  - "Ingeniero de software remoto"
  - "Programador remoto"
sitios:
  - "occ"
browser: "brave"
debugger_address: "127.0.0.1:9222"
controlled_mode: true
max_postulaciones_dia: 10
occ_max_scan_per_keyword: 12
```

### 6.1) Filtro de relevancia (todo desde `config.yaml`)

El bot decide si postular o no según el **título** de la vacante. Esa lógica se configura **solo** en `config.yaml` con el bloque `occ_filter` (no hace falta tocar código).

- **`exclude_terms`**: lista de textos. Si el título contiene alguno (case-insensitive), se **descarta** la vacante.  
  Ejemplo por defecto: `java `, `spring boot`, `springboot`, `hibernate`, `j2ee`, etc., para no postular a Java/Spring.
- **`exclude_regex`**: lista de expresiones regulares. Si alguna hace match con el título, se descarta. Útil para patrones más finos (ej. `.*php.*backend.*`).
- **`include_tech_terms`**: términos que **sí** te interesan. Si el título contiene alguno, se considera relevante (salvo que ya haya sido excluido).  
  Ejemplo: `react`, `frontend`, `typescript`, `next.js`, `node`, `python`, etc.
- **`keyword_ignore_tokens`**: palabras que se ignoran al extraer tokens de tus `keywords` para el fallback (ej. `remoto`, `méxico`, `junior`).

Orden interno: primero se aplican exclusiones; luego, si el título tiene algún `include_tech_terms`, se acepta; si no, se usa el fallback comparando tokens de la keyword con el título.

#### 6.2) Cómo personalizar sin tocar código

- **Evitar más tecnologías**: añade entradas a `occ_filter.exclude_terms` o `occ_filter.exclude_regex` en `config.yaml`.
- **Priorizar tu stack**: edita `occ_filter.include_tech_terms` (añade `golang`, `django`, `laravel`, etc.).
- **Afinar keywords**: cambia `keywords` y, si hace falta, `occ_filter.keyword_ignore_tokens`.

Cualquiera puede usar el bot solo editando `config.yaml`.

## 7) Qué hace el bot en OCC

- Busca por cada keyword en la URL de búsqueda de OCC.
- Recorre **todas las páginas** de resultados (paginación automática).
- Filtra vacantes con las reglas de `occ_filter` en `config.yaml` (excluir Java/Spring, priorizar tu stack, etc.).
- Para cada vacante relevante: abre la card, postula y resuelve el modal de conocimientos si aparece.
- Respeta límites: `max_postulaciones_dia` y `occ_max_scan_per_keyword`.

## 8) Evidencia y depuración

Se guardan capturas en `screenshots/` cuando hay errores.

Si falla el modal de conocimientos tras los reintentos:

- screenshot de modal (si disponible)
- screenshot de página
- log en `screenshots/occ_modal_failures.log` con `job_id` y contexto

## 9) Detener bot/procesos

```powershell
Get-CimInstance Win32_Process | Where-Object { ($_.Name -match '^python(\.exe)?$' -and $_.CommandLine -like '*PRUEBAS-PY\\bot*main.py*') -or ($_.Name -match '^chromedriver(\.exe)?$' -and $_.CommandLine -like '*PRUEBAS-PY\\bot*') -or ($_.Name -match '^brave(\.exe)?$' -and $_.CommandLine -like '*--remote-debugging-port=9222*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
```

## 10) Problemas comunes

- **No conecta al navegador**: Brave no está abierto con `--remote-debugging-port=9222`.
- **Se abre pero no postula**: revisa sesión iniciada en OCC y vacantes ya postuladas.
- **Mucho ruido en resultados**: ajusta `keywords` y baja/ajusta `occ_max_scan_per_keyword`.
- **Modal se atora**: revisar `screenshots/occ_modal_failures.log` y capturas.
