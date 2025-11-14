# Streamlit app - template for "Sistema de Sugerencias"
import os
import json
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
import sqlite3

load_dotenv()

from utils import (
    get_forecast_openweathermap,
    scrape_infoclima,
    suggest_for_week,
    call_gpt5_explanation,
)

DB_PATH = "stores.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        lat REAL,
        lon REAL,
        city TEXT,
        country TEXT,
        base_demand_json TEXT,
        created_at TEXT
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER,
        week_start TEXT,
        strategy TEXT,
        suggestion_json TEXT,
        explanation TEXT,
        created_at TEXT
    )""")
    conn.commit()
    conn.close()

def save_store(name, lat, lon, city, country, base_demand):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO stores (name, lat, lon, city, country, base_demand_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (name, lat, lon, city, country, json.dumps(base_demand), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def list_stores():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, lat, lon, city, country, base_demand_json FROM stores")
    rows = c.fetchall()
    conn.close()
    stores = []
    for r in rows:
        stores.append({
            "id": r[0], "name": r[1], "lat": r[2], "lon": r[3],
            "city": r[4], "country": r[5], "base_demand": json.loads(r[6])
        })
    return stores

def save_suggestion(store_id, week_start, strategy, suggestion, explanation):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO suggestions (store_id, week_start, strategy, suggestion_json, explanation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (store_id, week_start, strategy, json.dumps(suggestion), explanation, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

st.set_page_config(page_title="Sugerencias - Heladería", layout="wide")
init_db()

st.title("Sistema de Sugerencias - Heladería (MVP)")

tab = st.sidebar.radio("Navegación", ["Registrar tienda", "Ver tiendas", "Generar sugerencia", "Historial"])

if tab == "Registrar tienda":
    st.header("Registrar tienda")
    name = st.text_input("Nombre de la tienda")
    col1, col2 = st.columns(2)
    with col1:
        lat = st.text_input("Latitud (ej: -34.6037)")
        lon = st.text_input("Longitud (ej: -58.3816)")
    with col2:
        city = st.text_input("Ciudad")
        country = st.text_input("País")
    st.markdown("Puedes ingresar lat/lon manualmente o usar el botón 'Detectar ubicación' si tu navegador lo permite.")
    geoloc_html = """
    <button onclick="getLocation()">Detectar ubicación</button>
    <script>
    function getLocation() {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(function(position) {
          const coords = position.coords.latitude + ',' + position.coords.longitude;
          // Muestra las coordenadas para copiar/pegar en el formulario
          alert('Copiar al formulario: ' + coords);
        }, function(err){ alert('Error geolocalización: ' + err.message);});
      } else {
        alert('Geolocalización no soportada en este navegador');
      }
    }
    </script>
    """
    st.components.v1.html(geoloc_html, height=120)

    st.subheader("Valores base por producto (puedes ajustar)")
    default_base = {
        "palitos_u_per_day": 3.4,
        "conos_u_per_day": 3.0,
        "vasitos_u_per_day": 2.0,
        "potes_kg_per_day": 1.1,
        "helado_premium_kg_per_day": 0.6
    }
    base = st.text_area("JSON base (valores por día)", value=json.dumps(default_base, indent=2), height=150)
    if st.button("Guardar tienda"):
        try:
            base_parsed = json.loads(base)
            lat_f = float(lat) if lat else None
            lon_f = float(lon) if lon else None
            save_store(name, lat_f, lon_f, city, country, base_parsed)
            st.success("Tienda guardada.")
        except Exception as e:
            st.error(f"Error al guardar: {e}")

elif tab == "Ver tiendas":
    st.header("Tiendas registradas")
    stores = list_stores()
    if not stores:
        st.info("No hay tiendas registradas.")
    else:
        for s in stores:
            st.write(f"ID: {s['id']} — {s['name']} — {s['city']}, {s['country']} — lat:{s['lat']} lon:{s['lon']}")
            st.write("Base demand:", s['base_demand'])
            st.divider()

elif tab == "Generar sugerencia":
    st.header("Generar sugerencia semanal")
    stores = list_stores()
    store_map = {s['id']: s for s in stores}
    if not stores:
        st.info("Registra primero una tienda.")
    else:
        store_id = st.selectbox("Selecciona tienda", options=[s['id'] for s in stores], format_func=lambda x: f"{store_map[x]['name']} ({store_map[x]['city']})")
        strategy = st.selectbox("Estrategia", ["conservadora", "balanceada", "agresiva"])
        use_scrape = st.checkbox("Intentar usar infoclima (scraping) como fuente alternativa", value=False)
        source_choice = st.radio("Fuente pronóstico", ["OpenWeatherMap (recomendado)", "Infoclima (experimental)"], index=0 if not use_scrape else 1)

        store = store_map[store_id]
        if st.button("Generar"):
            lat = store["lat"]
            lon = store["lon"]
            if lat is None or lon is None:
                st.error("La tienda no tiene latitud/longitud. Edita la tienda y agrega coordenadas.")
            else:
                try:
                    if source_choice.startswith("OpenWeatherMap"):
                        forecast = get_forecast_openweathermap(lat, lon)
                    else:
                        # Intentar scrape; si falla, usar OWM como fallback
                        try:
                            forecast = scrape_infoclima(lat, lon)
                        except RuntimeError as e:
                            st.warning(f"Scraping infoclima falló: {e}")
                            st.info("Usando OpenWeatherMap como fuente alternativa.")
                            forecast = get_forecast_openweathermap(lat, lon)
                    suggestion = suggest_for_week(forecast, store["base_demand"], strategy=strategy)
                except Exception as e:
                    st.error(f"Error generando sugerencia: {e}")
                    st.stop()

                # Generar explicación con GPT-5 mini (placeholder)
                expl_prompt = f"Genera 3-4 frases explicando estas sugerencias y recomendaciones de stock para la semana según este pronóstico y la estrategia {strategy}: {suggestion}"
                explanation = call_gpt5_explanation(expl_prompt)

                st.subheader("Sugerencias")
                st.json(suggestion)
                st.subheader("Explicación (GPT-5 mini)")
                st.write(explanation)
                # persist
                save_suggestion(store_id, suggestion.get("week_start", ""), strategy, suggestion, explanation)
                st.success("Sugerencia guardada en historial.")

elif tab == "Historial":
    st.header("Historial de sugerencias")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT s.id, st.name, s.week_start, s.strategy, s.suggestion_json, s.explanation, s.created_at FROM suggestions s JOIN stores st ON s.store_id = st.id ORDER BY s.created_at DESC")
    rows = c.fetchall()
    conn.close()
    if not rows:
        st.info("No hay sugerencias guardadas aún.")
    else:
        for r in rows:
            st.markdown(f"### {r[1]} — {r[2]} — {r[3]}")
            st.json(json.loads(r[4]))
            st.write("Explicación:")
            st.write(r[5])
            st.write("Creada:", r[6])
            st.divider()
