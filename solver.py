import osmnx as ox
import networkx as nx
from pyomo.environ import *
import matplotlib.pyplot as plt
import io
import base64

def parsear_coordenadas(lista):
    return [tuple(map(float, coord.strip().split(','))) for coord in lista]

def resolver_ruta_optima(lista_coordenadas):
    print("Cargando grafo de Bogotá...")
    G = ox.graph_from_place("Bogotá, Colombia", network_type='drive')
    
    coordenadas = parsear_coordenadas(lista_coordenadas)
    nodos = [ox.distance.nearest_nodes(G, lon, lat) for lat, lon in coordenadas]

    # Construir ruta por tramos consecutivos
    ruta_total = []
    for i in range(len(nodos) - 1):
        tramo = nx.shortest_path(G, nodos[i], nodos[i+1], weight='length')
        if i > 0:
            tramo = tramo[1:]
        ruta_total.extend(tramo)

    # Crear conjunto de arcos y distancias
    arcos = []
    distancias = {}
    for u, v in zip(ruta_total[:-1], ruta_total[1:]):
        d = G[u][v][0]['length'] / 1000
        arcos.append((u, v))
        distancias[(u, v)] = d
    nodos_unicos = set([n for a in arcos for n in a])

    # Modelo Pyomo
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

    solver = SolverFactory('cbc')
    result = solver.solve(model)

    ruta_optima = [i for i in model.A if value(model.x[i]) == 1]
    nodos_ruta = [ruta_optima[0][0]] + [a[1] for a in ruta_optima]

    # Imagen en JPG codificada en base64
    fig, ax = ox.plot_graph_route(G, nodos_ruta, route_color='orange', node_size=0, show=False, close=False)
    buf = io.BytesIO()
    fig.savefig(buf, format='jpg', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    imagen_base64 = base64.b64encode(buf.read()).decode('utf-8')

    # Coordenadas para Google Maps
    coordenadas_ruta = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in nodos_ruta]
    base_url = "https://www.google.com/maps/dir/"
    google_maps_url = base_url + "/".join([f"{lat},{lon}" for lat, lon in coordenadas_ruta])

    return {
        "nodos": nodos_ruta,
        "google_maps_url": google_maps_url,
        "imagen_jpg_base64": imagen_base64
    }
