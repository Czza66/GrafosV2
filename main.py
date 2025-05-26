from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List
import osmnx as ox
import networkx as nx
from pyomo.environ import *
import folium
import uuid
import os
import matplotlib.pyplot as plt
import io
import base64

from mapa import generar_mapa

app = FastAPI(title="API de Ruta Óptima")
templates = Jinja2Templates(directory="templates")

# Cargar el grafo de Bogotá una sola vez
print("Cargando grafo de Bogotá...")
G = ox.graph_from_place("Bogotá, Colombia", network_type='drive')


class CoordenadasInput(BaseModel):
    coordenadas: List[float]  # Lista plana: lat1, lon1, lat2, lon2, ...


@app.post("/ruta-optima/")
def calcular_ruta_optima(data: CoordenadasInput):
    try:
        coords = data.coordenadas
        if len(coords) < 4 or len(coords) % 2 != 0:
            raise HTTPException(status_code=400, detail="La lista debe contener pares de coordenadas (lat, lon)")

        puntos = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
        nodos = [ox.distance.nearest_nodes(G, lon, lat) for lat, lon in puntos]

        ruta_total = []
        for i in range(len(nodos) - 1):
            ruta = nx.shortest_path(G, nodos[i], nodos[i + 1], weight='length')
            if i > 0:
                ruta = ruta[1:]
            ruta_total += ruta

        arcos = []
        distancias = {}
        for u, v in zip(ruta_total[:-1], ruta_total[1:]):
            d = G[u][v][0]['length'] / 1000
            arcos.append((u, v))
            distancias[(u, v)] = d
        nodos_unicos = set(n for arco in arcos for n in arco)

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

        solver = SolverFactory('glpk')
        result = solver.solve(model, tee=False)

        if result.solver.status != SolverStatus.ok:
            raise HTTPException(status_code=500, detail="No se pudo resolver el modelo")

        ruta_optima = [i for i in model.A if value(model.x[i]) == 1]
        distancia_total = sum(distancias[i] for i in ruta_optima)
        nodos_ruta = [ruta_optima[0][0]] + [a[1] for a in ruta_optima]

        coordenadas = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in nodos_ruta]
        mapa_id = generar_mapa(coordenadas)

        # ======== NUEVO: Imagen del grafo con ruta (en base64) ========
        fig, ax = ox.plot_graph_route(
            G, nodos_ruta, route_color='red', route_linewidth=4, node_size=0,
            show=False, close=False
        )

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        # ===============================================================

        return {
            "distancia_total_km": round(distancia_total, 2),
            "ruta": coordenadas,
            "mapa_url": f"/ver-mapa/{mapa_id}",
            "grafo_img_base64": img_base64
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mapa/{mapa_id}")
def ver_mapa_archivo(mapa_id: str):
    file_path = f"mapas/{mapa_id}.html"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Mapa no encontrado")
    return FileResponse(file_path, media_type='text/html')


@app.get("/ver-mapa/{mapa_id}", response_class=HTMLResponse)
def mostrar_mapa(request: Request, mapa_id: str):
    mapa_path = f"/mapa/{mapa_id}"
    return templates.TemplateResponse("ver_url.html", {
        "request": request,
        "mapa_path": mapa_path
    })
