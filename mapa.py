import os
import folium
import uuid

MAPAS_DIR = "mapas"
os.makedirs(MAPAS_DIR, exist_ok=True)

def generar_mapa(ruta_coords):
    mapa_id = str(uuid.uuid4())
    mapa = folium.Map(location=ruta_coords[0], zoom_start=14)
    folium.PolyLine(ruta_coords, color="blue", weight=5).add_to(mapa)
    output_path = os.path.join(MAPAS_DIR, f"{mapa_id}.html")
    mapa.save(output_path)
    return mapa_id
