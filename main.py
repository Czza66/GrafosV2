from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import osmnx as ox
import networkx as nx
from pyomo.environ import *
import folium
import uuid
import os

app = FastAPI(title="API de Ruta Óptima")

# Cargar el grafo de Bogotá una sola vez
print("Cargando grafo de Bogotá...")
G = ox.graph_from_place("Bogotá, Colombia", network_type='drive')

# Input esperado
class CoordenadasInput(BaseModel):
    coordenadas: List[float]  # Lista plana: lat1, lon1, lat2, lon2, ...

@app.post("/ruta-optima/")
def calcular_ruta_optima(data: CoordenadasInput):
    try:
        coords = data.coordenadas
        if len(coords) < 4 or len(coords) % 2 != 0:
            raise HTTPException(status_code=400, detail="La lista debe contener pares de coordenadas (lat, lon)")

        # Convertir a lista de tuplas (lat, lon)
        puntos = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]

        # Obtener nodos más cercanos
        nodos = [ox.distance.nearest_nodes(G, lon, lat) for lat, lon in puntos]

        # Calcular la ruta secuencial
        ruta_total = []
        for i in range(len(nodos) - 1):
            ruta = nx.shortest_path(G, nodos[i], nodos[i + 1], weight='length')
            if i > 0:
                ruta = ruta[1:]
            ruta_total += ruta

        # Crear arcos y distancias
        arcos = []
        distancias = {}
        for u, v in zip(ruta_total[:-1], ruta_total[1:]):
            d = G[u][v][0]['length'] / 1000  # km
            arcos.append((u, v))
            distancias[(u, v)] = d
        nodos_unicos = set(n for arco in arcos for n in arco)

        # Modelo con Pyomo
        model = ConcreteModel()
        model.A = Set(initialize=arcos, dimen=2)
        model.N = Set(initialize=nodos_unicos)
        model.x = Var(model.A, domain=Binary)

        model.obj = Objective(expr=sum(distancias[i] * model.x[i] for i in model.A), sense=minimize)

        def flujo_balance(model, n):
            if n == nodos[0]:
                return sum(model.x[i] for i in model.A if i[0] == n) == 1
            elif n == nodos[-1]:
                return sum(model.x[i] for i in model.A if i[1] == n) == 1
            else:
                return (sum(model.x[i] for i in model.A if i[0] == n) -
                        sum(model.x[i] for i in model.A if i[1] == n)) == 0

        model.flujo = Constraint(model.N, rule=flujo_balance)

        # Resolver
        solver = SolverFactory('glpk')
        result = solver.solve(model, tee=True)

        if result.solver.status != SolverStatus.ok:
            raise HTTPException(status_code=500, detail="No se pudo resolver el modelo")

        ruta_optima = [i for i in model.A if value(model.x[i]) == 1]
        distancia_total = sum(distancias[i] for i in ruta_optima)
        nodos_ruta = [ruta_optima[0][0]] + [a[1] for a in ruta_optima]

        # Crear mapa
        lat, lon = G.nodes[nodos_ruta[0]]['y'], G.nodes[nodos_ruta[0]]['x']
        mapa = folium.Map(location=[lat, lon], zoom_start=12)
        for nodo in nodos_ruta:
            lat = G.nodes[nodo]['y']
            lon = G.nodes[nodo]['x']
            folium.CircleMarker(location=(lat, lon), radius=3, color='blue', fill=True).add_to(mapa)
        coordenadas = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in nodos_ruta]
        folium.PolyLine(coordenadas, color="orange", weight=3, opacity=0.8).add_to(mapa)

        # Guardar HTML del mapa
        map_id = str(uuid.uuid4())
        os.makedirs("mapas", exist_ok=True)
        file_path = f"mapas/{map_id}.html"
        mapa.save(file_path)

        return {
            "distancia_total_km": round(distancia_total, 2),
            "ruta": coordenadas,
            "mapa_url": f"/mapa/{map_id}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mapa/{mapa_id}")
def ver_mapa(mapa_id: str):
    file_path = f"mapas/{mapa_id}.html"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Mapa no encontrado")
    return FileResponse(file_path, media_type='text/html')
