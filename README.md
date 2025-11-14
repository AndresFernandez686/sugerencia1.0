```markdown
# Sistema de Sugerencias - Template (MVP)

Este repo contiene un template Streamlit que implementa el plan de sugerencias semanales para heladerías:
- Registro de tienda (lat/lon, ciudad)
- Obtención de pronóstico 7 días (OpenWeatherMap por defecto; scraping experimental de infoclima como fallback)
- Cálculo de sugerencias por producto (bultos / cajas) usando tus reglas de factores térmicos y estrategia
- Generación de explicación usando GPT-5 mini (endpoint configurable)

Requisitos
- Python 3.9+
- Claves en .env:
  - OWM_API_KEY: OpenWeatherMap One Call API key
  - GPT5_API_URL: endpoint HTTP de tu GPT-5 mini (ajusta según tu proveedor)
  - GPT5_API_KEY: clave para el servicio GPT-5 mini

Instalación
1. Clonar y crear entorno:
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt

2. Crear .env con tus claves (ver .env.example).

3. Ejecutar:
   streamlit run app.py

Notas importantes sobre fuentes meteorológicas y scraping
- Recomendación: usa APIs oficiales (OpenWeatherMap, WeatherAPI, Meteostat, VisualCrossing). Son precisas, ofrecen históricos, y su uso está pensado para integraciones.
- Scraping de páginas públicas (ej: infoclima.com) es posible como complemento experimental, pero:
  - Puede romper si cambia la estructura del HTML.
  - Puede violar los Términos de Servicio del sitio; revisa ToS antes de usarlo en producción.
  - No es tan fiable ni escalable como una API.
- LLM (GPT-5 mini):
  - Un LLM no "sabe" el clima actual por sí mismo; necesita que le pases el pronóstico o la página scrapeada como contexto para generar explicaciones.
  - GPT-5 mini se usa para redactar las explicaciones/recomendaciones a partir de los números que tú le des.
  - Ten en cuenta costos por llamada; cachea explicaciones por tienda/semana para ahorrar.

Siguientes pasos sugeridos
- Automatizar recomputos con cron / APScheduler / Prefect (ej. script scheduler.py).
- Guardar histórico de ventas reales para entrenar modelos de forecasting que usen pronóstico meteorológico como exógena.
- Sustituir scraping por proveedores con SLAs si escalas.

```
