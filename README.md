# ChambaFlow — Automatización de Postulaciones

Bot de automatización para postular en OCC y Computrabajo (México) usando Python y Selenium. Se conecta a una sesión activa del navegador para operar con tu cuenta real, aplicando filtros configurables por keywords, tecnologías y límite diario de postulaciones.

**Stack:** Python · Selenium · WebDriver Manager · PyYAML · Questionary

## Características

- Soporte para OCC (scroll infinito + filtros por términos) y Computrabajo (formulario in-page + envío de CV)
- Menú interactivo en consola para elegir sitios en cada ejecución
- Configuración centralizada en `config.yaml`: keywords, filtros de exclusión/inclusión, ruta del CV, límite diario
- Compatible con Brave y Chrome vía remote debugging port
- Ejecutable por CLI con flags `--sitios` para integración en scripts o automatizaciones

## Requisitos

- Python 3.10+
- Brave o Chrome
- Sesión activa iniciada manualmente en OCC y/o Computrabajo

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
python -u main.py
```

```bash
# O directamente por CLI
python -u main.py --sitios computrabajo
python -u main.py --sitios occ,computrabajo
```
