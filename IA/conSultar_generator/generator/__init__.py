"""
Paquete `generator`: lógica del generador de la aplicación web ConSultar.

Módulos:
    config.py      - Carga y modelado tipado de la configuración (YAML/JSON).
    validators.py  - Validación semántica de la configuración cargada.
    templates.py   - Entorno Jinja2 y renderizado de las plantillas.
    generator.py   - Orquestación del proceso completo (cargar → validar →
                      renderizar → escribir).
"""
