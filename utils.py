# Utilities for forecasts, scraping and suggestion calculation
import os
import requests
from datetime import datetime

OWM_KEY = os.getenv("OWM_API_KEY")
GPT5_API_URL = os.getenv("GPT5_API_URL")  # endpoint de GPT-5 mini (configurable)
GPT5_API_KEY = os.getenv("GPT5_API_KEY")

def get_forecast_openweathermap(lat, lon):
    """
    Consulta One Call API de OpenWeatherMap y devuelve lista de 'daily' con campos:
    [{'dt': timestamp, 'temp': {'min':.., 'max':..}, 'pop': precip_prob, ...}, ...]
    """
    if lat is None or lon is None:
        raise RuntimeError("Latitud/longitud no proporcionadas para OpenWeatherMap.")
    if not OWM_KEY:
        raise RuntimeError("OWM_API_KEY no configurada en .env")
    url = f"https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,alerts&units=metric&appid={OWM_KEY}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data.get("daily", [])[:7]

def scrape_infoclima(lat, lon):
    """
    Método experimental: intenta obtener pronóstico desde infoclima.com
    - Import de BeautifulSoup se hace aquí para evitar fallos en el import del módulo si bs4 no está instalado.
    - Puede fallar si la web cambia o si el sitio bloquea scraping.
    - Usar solo como fallback o para comparativa; revisar ToS del sitio antes de producción.
    """
    try:
        from bs4 import BeautifulSoup
    except Exception:
        raise RuntimeError(
            "beautifulsoup4 no está instalado. Instala dependencias ejecutando 'pip install beautifulsoup4' "
            "o añade 'beautifulsoup4' a requirements.txt y vuelve a desplegar."
        )

    # Infoclima no tiene endpoint público con lat/lon; este es un ejemplo heurístico y debe ajustarse según la página real.
    base_url = "https://infoclima.com/?ch=PY"
    r = requests.get(base_url, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    daily = []
    # Selector hipotético — adaptar según la estructura real de la web
    days = soup.select(".forecast .day")
    for d in days[:7]:
        try:
            date_elem = d.select_one(".date")
            min_elem = d.select_one(".min")
            max_elem = d.select_one(".max")
            if not (date_elem and min_elem and max_elem):
                continue
            temp_min = float(min_elem.get_text().strip().replace("°","").replace("C","").strip())
            temp_max = float(max_elem.get_text().strip().replace("°","").replace("C","").strip())
            daily.append({"dt": int(datetime.now().timestamp()), "temp": {"min": temp_min, "max": temp_max}})
        except Exception:
            continue

    if not daily:
        raise RuntimeError("No se pudo parsear infoclima (estructura cambiada o selectores incorrectos).")
    return daily

def thermal_factor(temp_c):
    if temp_c < 20:
        return 0.3
    if temp_c < 25:
        return 1.0
    if temp_c < 30:
        return 1.8
    return 2.5

def day_factor(date_obj):
    # Ejemplo simple: fines de semana aumentan demanda
    if date_obj.weekday() in (5,6):
        return 1.4
    return 1.0

def suggest_for_week(forecast_daily, base_demand_per_product, strategy="balanceada"):
    """
    forecast_daily: lista de 7 items con 'dt' y 'temp' {'min','max'}
    base_demand_per_product: dict con demandas por día (u/day o kg/day)
    strategy: "conservadora", "balanceada", "agresiva"
    """
    # strategy multipliers for buffer/risk
    strat_multiplier = {"conservadora": 0.9, "balanceada": 1.0, "agresiva": 1.15}
    mult = strat_multiplier.get(strategy, 1.0)

    weekly = {}
    week_start = datetime.utcfromtimestamp(forecast_daily[0]["dt"]).date().isoformat() if forecast_daily else datetime.utcnow().date().isoformat()
    # Inicializar acumuladores semanales
    for prod in base_demand_per_product:
        weekly[prod] = 0.0

    # Sumar demanda prevista por cada día del pronóstico
    for day in forecast_daily:
        date = datetime.utcfromtimestamp(day["dt"])
        temp_mean = (day["temp"]["min"] + day["temp"]["max"]) / 2.0
        tf = thermal_factor(temp_mean)
        df = day_factor(date)
        for prod, base_day in base_demand_per_product.items():
            # base_day representa demanda diaria base; sumamos día a día
            weekly[prod] += base_day * tf * df

    # Convertir a bultos/cajas según reglas:
    suggestions = {"week_start": week_start, "strategy": strategy, "items": []}
    for prod, total_week in weekly.items():
        adjusted = total_week * mult  # ajuste por estrategia
        if prod.startswith("palitos") or prod.endswith("_u_per_day"):
            # total_week ya es unidades por semana (porque sumamos día a día)
            units_week = round(adjusted, 1)
            bultos = round(units_week / 24, 1)
            suggestions["items"].append({"product": prod, "units_week": units_week, "bultos": bultos})
        else:
            # asume keys de kg diarias terminan con _kg_per_day
            kg_week = round(adjusted, 1)
            cajas = round(kg_week / 7.8, 1)
            suggestions["items"].append({"product": prod, "kg_week": kg_week, "cajas": cajas})
    return suggestions

def call_gpt5_explanation(prompt_text):
    """
    Llamada genérica a tu endpoint GPT-5 mini. Ajusta según proveedor.
    Se espera que el endpoint acepte JSON: {'prompt': str} y devuelva {'text': str}
    """
    if not GPT5_API_URL or not GPT5_API_KEY:
        return "(GPT no configurado) Explicación no generada. Configure GPT5_API_URL y GPT5_API_KEY en .env"
    headers = {"Authorization": f"Bearer {GPT5_API_KEY}", "Content-Type": "application/json"}
    body = {"prompt": prompt_text, "max_tokens": 200}
    try:
        r = requests.post(GPT5_API_URL, json=body, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("text") or data.get("output") or str(data)
    except Exception as e:
        return f"(Error llamando GPT): {e}"
